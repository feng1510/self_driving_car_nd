import os
import sys
import csv
import cv2
import numpy as np
from keras.layers import Lambda, Cropping2D, Conv2D, Flatten, Dense
from keras.models import Sequential
from keras.callbacks import ModelCheckpoint
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle
import tensorflow as tf
from datetime import datetime
import matplotlib.pyplot as plt
from collections import namedtuple
import enum

flags = tf.app.flags
FLAGS = flags.FLAGS

# command line flags
flags.DEFINE_string('output_dir', './training_output/', "Output path for trained model and training information.")
flags.DEFINE_string('driving_log_dir', './data/example_data/', "Path to simulator driving log directories.")
flags.DEFINE_integer('epochs', 3, "Number of epochs to train")
flags.DEFINE_integer('batch_size', 32, "Batch size")
flags.DEFINE_float('steering_offset', 0.02, "Steering offset for left and right camera images.")
flags.DEFINE_float('sharp_turn_threshold', 0.05, ("A steering value greater than this during normal driving is",
                                                  "assumed to be in a sharp curve."))


class SequenceType(enum.Enum):
    NORMAL = 1,
    OTHER_DIRECTION = 2,
    RECOVERY_ACTION = 3,
    TIGHT_CURVE = 4,


class CamType(enum.Enum):
    CENTER = 1,
    LEFT = 2,
    RIGHT = 3,


def load_driving_logs():
    """Loads all logs available in driving_log_dir.

    Returns:
        Dictionary of logs, where directory names are used as keys.
    """
    assert(os.path.exists(FLAGS.driving_log_dir))
    driving_logs = dict()
    for (dir_path, dir_names, file_names) in os.walk(FLAGS.driving_log_dir):
        if 'driving_log.csv' in file_names:
            sequence_type, log = load_driving_log(dir_path)
            driving_logs[sequence_type] = log
    return driving_logs


def load_driving_log(dir_path):
    """Load driving log located in selected directory.

    Returns:
        sequence_type -- defined by dir name
        log -- list of samples
    """
    file_path = os.path.join(dir_path, 'driving_log.csv')
    assert(os.path.exists(file_path))
    image_path = os.path.join(dir_path, 'IMG')
    assert(os.path.exists(image_path))

    _, name = os.path.split(dir_path)
    sequence_type = dir_name_to_sequence_type(name)
    print(f"Loading {name} as {sequence_type}")
    log = []
    with open(file_path) as csv_file:
        reader = csv.DictReader(csv_file,
                                fieldnames=['center', 'left', 'right', 'steering', 'throttle', 'brake', 'speed'])
        for line in reader:
            log.append(fix_paths(line, image_path))

    return sequence_type, log


def dir_name_to_sequence_type(name):
    # Map directory names to SequenceType
    sequence_type_lookup = {
        'normal': SequenceType.NORMAL,
        'other_direction': SequenceType.OTHER_DIRECTION,
        'recovery': SequenceType.RECOVERY_ACTION,
        'tight_curves': SequenceType.TIGHT_CURVE,
    }
    try:
        sequence_type = sequence_type_lookup[name]
    except KeyError:
        print(f"Please name driving log directory {name} one of {list(sequence_type_lookup.keys())}")
        sys.exit(1)

    return sequence_type


def fix_paths(csv_line, correct_path):
    """Correct file paths in read log data.

    The simulator outputs absolute paths to the log file, which becomes corrupt
    when the log is moved to another directory.
    """
    _, file_name = os.path.split(csv_line['center'])
    csv_line['center'] = os.path.join(correct_path, file_name)
    _, file_name = os.path.split(csv_line['left'])
    csv_line['left'] = os.path.join(correct_path, file_name)
    _, file_name = os.path.split(csv_line['right'])
    csv_line['right'] = os.path.join(correct_path, file_name)
    return csv_line


Sample = namedtuple('Sample', ['image_path', 'steering', 'sequence_type', 'cam_type'])


def driving_logs_to_samples(driving_logs):
    """Combine several driving logs into one list of samples

    Arguments:
        driving_logs -- Dictionary of logs, where directory names are used as keys.
    """
    samples = []
    for sequence_type, log in driving_logs.items():
        # Use all available log entries.
        samples += log_to_samples(log, sequence_type)

    return samples


def log_to_samples(log, sequence_type):
    samples = []
    for log_entry in log:
        steering = float(log_entry['steering'])
        samples.append(Sample(image_path=log_entry['center'],
                              steering=steering,
                              sequence_type=sequence_type,
                              cam_type=CamType.CENTER))
        samples.append(Sample(image_path=log_entry['left'],
                              steering=steering,
                              sequence_type=sequence_type,
                              cam_type=CamType.LEFT))
        samples.append(Sample(image_path=log_entry['right'],
                              steering=steering,
                              sequence_type=sequence_type,
                              cam_type=CamType.RIGHT))

    return samples


def filter_samples(samples):
    """Remove samples causing worse result.

    Arguments:
        samples -- List of samples

    Returns:
        samples -- Filtered list of samples
    """
    # Use left and right camera only to stabilize when going fairly straight during normal driving.
    samples = list(filter(lambda sample:
                          (sample.cam_type is CamType.CENTER or
                           (sample.sequence_type in [SequenceType.NORMAL, SequenceType.OTHER_DIRECTION] and
                            abs(sample.steering) < FLAGS.sharp_turn_threshold)),
                          samples))

    return samples


def adjust_steering(samples):
    """Adjust steering angles

    Apply a steering offset to left and right camera samples towards center.

    Arguments:
        samples -- List of samples to be adjusted.

    Returns:
        samples -- Adjusted list of samples
    """
    for i in range(len(samples)):
        steering = samples[i].steering
        if samples[i].cam_type is CamType.LEFT:
            samples[i] = samples[i]._replace(steering=steering + FLAGS.steering_offset)
        elif samples[i].cam_type is CamType.RIGHT:
            samples[i] = samples[i]._replace(steering=steering - FLAGS.steering_offset)
        else:
            # Do nothing for center camera.
            pass
    return samples


def batch_generator(samples):
    while 1:  # Loop forever so the generator never terminates
        shuffle(samples)
        for offset in range(0, len(samples), FLAGS.batch_size):
            batch_samples = samples[offset:offset + FLAGS.batch_size]

            images = []
            angles = []
            for batch_sample in batch_samples:
                images.append(cv2.imread(batch_sample.image_path))
                angles.append(batch_sample.steering)

            X_train = np.array(images)
            y_train = np.array(angles)
            yield shuffle(X_train, y_train)


def define_model(input_shape=(160, 320, 3)):
    """Defines the model to be trained.

    Implements something similar to the architecture described here:
    https://devblogs.nvidia.com/parallelforall/deep-learning-self-driving-cars/

    Returns:
        A Keras model
    """
    model = Sequential()

    # Preprocess incoming data, centered around zero with small standard deviation
    model.add(Lambda(lambda x: (x / 255.0) - 0.5, input_shape=input_shape))

    # Remove some parts of the sky/background (first 70 rows) and the vehicle hood (last 25 rows).
    model.add(Cropping2D(cropping=((70, 25), (0, 0))))

    # Neural network layers
    model.add(Conv2D(24, (5, 5), strides=(2, 2), activation='relu'))
    model.add(Conv2D(36, (5, 5), strides=(2, 2), activation='relu'))
    model.add(Conv2D(48, (5, 5), strides=(2, 2), activation='relu'))
    model.add(Conv2D(64, (3, 3), strides=(1, 1), activation='relu'))
    model.add(Conv2D(64, (3, 3), strides=(1, 1), activation='relu'))
    model.add(Flatten())
    model.add(Dense(100, activation='relu'))
    model.add(Dense(50, activation='relu'))
    model.add(Dense(10, activation='relu'))
    model.add(Dense(1, activation='tanh'))

    return model


def create_output_dir():
    """Generate an output dir for this training

    Current time-stamp is used to create a unique name for this training.

    Returns:
        Path to created directory
    """
    training_name = datetime.now().strftime('%Y%m%d-%H%M%S')
    training_dir = os.path.join(FLAGS.output_dir, training_name)
    assert(not os.path.exists(training_dir))
    os.makedirs(training_dir)
    print(f"Training output goes to {training_dir}")

    return training_dir


def setup_callbacks_list(output_path):
    """Setup a list of training callbacks"""
    file_path = os.path.join(output_path, "weights-improvement-{epoch:02d}-{val_loss:.5f}.hdf5")
    checkpoint = ModelCheckpoint(file_path, monitor='val_loss', verbose=1, save_best_only=False, mode='min')
    return [checkpoint]  # Currently only one callback


def plot_training_history_to_file(history_object, output_dir):
    """Plot training history

    Plot training and validation loss from each epoch

    Arguments:
        history_object -- provided by keras fit
        output_dir -- the figure is output as file
    """
    plt.plot(history_object.history['loss'])
    plt.plot(history_object.history['val_loss'])
    plt.title('Mean Squared Error (MSE)')
    plt.ylabel('MSE')
    plt.xlabel('epoch')
    plt.legend(['training', 'validation'], loc='upper right')
    plt.savefig(os.path.join(output_dir, 'training_result.png'), bbox_inches='tight')


def model_to_text_file(model, output_dir):
    try:
        with open(os.path.join(output_dir, 'model.txt'), 'w') as fid:
            model.summary(print_fn=lambda x: fid.write(x + '\n'))
    except TypeError:
        # Model summary print_fn wasn't implemented until Keras 2.0.6.
        print("Please update Keras library to >2.0.6 to get model summary written to file.")

    with open(os.path.join(output_dir, 'model.txt'), 'a') as fid:
        print("\nArguments:", file=fid)
        for key, value in FLAGS.__flags.items():
            print(key, value, file=fid)


def output_result(output_path, model, history_object):
    plot_training_history_to_file(history_object, output_path)
    model_to_text_file(model, output_path)


def main(_):
    output_path = create_output_dir()
    driving_logs = load_driving_logs()
    samples = driving_logs_to_samples(driving_logs)
    samples = filter_samples(samples)
    samples = adjust_steering(samples)

    train_samples, validation_samples = train_test_split(samples, test_size=0.2)

    train_generator = batch_generator(train_samples)
    validation_generator = batch_generator(validation_samples)

    model = define_model()
    model.compile(loss='mse', optimizer='adam')

    callbacks_list = setup_callbacks_list(output_path)
    history_object = model.fit_generator(train_generator, epochs=FLAGS.epochs,
                                         steps_per_epoch=(len(train_samples) // FLAGS.batch_size),
                                         validation_data=validation_generator,
                                         validation_steps=(len(validation_samples) // FLAGS.batch_size),
                                         callbacks=callbacks_list, verbose=1)
    output_result(output_path, model, history_object)


if __name__ == '__main__':
    tf.app.run()