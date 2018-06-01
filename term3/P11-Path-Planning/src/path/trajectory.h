#ifndef TRAJECTORY_H
#define TRAJECTORY_H

#include <climits>
#include <string>
#include <vector>
#include "../helpers.h"
#include "../vehicle_data.h"
#include "logic.h"

#define NO_LANE_CHANGE_START_IDX (INT_MIN)

namespace Path {
  class Trajectory {
  public:
    Trajectory();
    Trajectory(std::vector<double> x, std::vector<double> y);
    std::vector<double> x;
    std::vector<double> y;
    std::vector<Logic::Intention> intention;
    std::vector<int> targetLane;
    int laneChangeStartIdx;

    void set(int idx, double x_, double y_);
    void set(int idx, double x_, double y_, Logic::Intention intention_, int targetLane_);

    void push_back(double x_, double y_);
    void push_back(double x_, double y_, Logic::Intention intention_, int targetLane_);

    /** Concatenate two trajectories. */
    Trajectory operator+(const Trajectory &other) const {
      Trajectory result = *this;
      if (other.laneChangeStartIdx != NO_LANE_CHANGE_START_IDX) {
        result.laneChangeStartIdx = result.size() + other.laneChangeStartIdx;
      }
      result.x.insert(result.x.end(), other.x.begin(), other.x.end());
      result.y.insert(result.y.end(), other.y.begin(), other.y.end());
      result.intention.insert(result.intention.end(), other.intention.begin(), other.intention.end());
      result.targetLane.insert(result.targetLane.end(), other.targetLane.begin(), other.targetLane.end());
      return result;
    }

    /** Concatenate a trajectory to this trajectory. */
    void operator+=(const Trajectory &other) {
      if (other.laneChangeStartIdx != NO_LANE_CHANGE_START_IDX) {
        laneChangeStartIdx = size() + other.laneChangeStartIdx;
      }
      x.insert(x.end(), other.x.begin(), other.x.end());
      y.insert(y.end(), other.y.begin(), other.y.end());
      intention.insert(intention.end(), other.intention.begin(), other.intention.end());
      targetLane.insert(targetLane.end(), other.targetLane.begin(), other.targetLane.end());
    }

    /** Output stream operator providing all coordinates. */
    friend std::ostream& operator<<(std::ostream &os, const Trajectory &m) {
      os.precision(10);
      os << std::fixed;
      for (int i = 0; i < m.size(); ++i) {
        if (i == m.laneChangeStartIdx) {
          os << "Lane change start here! ";
        }
        os << "(" << m.intention[i] << " to lane " << m.targetLane[i] << ": " << m.x[i] << ", " << m.y[i] << "), ";
      }
      return os;
    }

    /** Provides the number of coordinates in the trajectory. */
    int size() const;

    /** Erase a range of coordinates from the trajectory.
     * @param startIdx Start coordinate in range to erase.
     * @param endIdx End coordinate in range to erase (inclusive).
     */
    void erase(int startIdx, int endIdx);
    /** Get an approximation of vehicle state at the end of the trajectory.
     * This is useful when concatenating trajectories. The result seems to
     * be smooth enough for the simulator.
     */
    VehicleData::EgoVehicleData getEndState(const VehicleData::EgoVehicleData &startState) const;
    VehicleData::EgoVehicleData getState(const VehicleData::EgoVehicleData &startState, int idx) const;

    /** Trajectory kinematics estimations. */
    class Kinematics {
    public:
      std::vector<double> speeds;
      std::vector<double> accelerations;
      std::vector<double> jerks;
      std::vector<double> yaws;
      std::vector<double> yawRates;

      /** Output stream operator providing all kinematics for the trajectory. */
      friend std::ostream& operator<<(std::ostream &os, const Kinematics &m) {
        int i = 0u;
        for (; i < m.jerks.size(); ++i) {
          os << i <<
                ", speed = " << m.speeds[i] <<
                ", yaw = " << m.yaws[i] <<
                ", acc = " << m.accelerations[i] <<
                ", yawRate = " << m.yawRates[i] <<
                ", jerk = " << m.jerks[i] <<
                  std::endl;
        }
        for (; i < m.accelerations.size(); ++i) {
          os << i <<
                ", speed = " << m.speeds[i] <<
                ", yaw = " << m.yaws[i] <<
                ", acc = " << m.accelerations[i] <<
                ", yawRate = " << m.yawRates[i] <<
                  std::endl;
        }
        for (; i < m.speeds.size(); ++i) {
          os << i <<
                ", speed = " << m.speeds[i] <<
                ", yaw = " << m.yaws[i] <<
                  std::endl;
        }
        return os;
      };
    };

    /** Provides kinematics values for the trajectory. */
    Kinematics getKinematics() const;
  };

  namespace TrajectoryCalculator {
    /** Apply optimal acceleration to reach delta_speed.
     * The d coordinate is kept constant, e.g. the vehicle stays in the same lane.
     *
     * @param intention The intention of this trajectory, propagated to each coordinate.
     * @param targetLane The ultimate target lane of this trajectory. Note, this is only propagated and does not change the coordinates of the trajectory.
     * @param start Ego vehicle state at start of this trajectory.
     * @param delta_speed The speed change to apply in this trajectory.
     */
    Trajectory Accelerate(Logic::Intention intention, int targetLane, const VehicleData::EgoVehicleData &start, double delta_speed);
    /** Extend vector by a number of coordinates.
     * The speed and d coordinate is kept constant. */
    Trajectory ConstantSpeed(Logic::Intention intention, const VehicleData::EgoVehicleData &start, int numCoords);
    Trajectory Others(const VehicleData::OtherVehicleData &start, int numCoords);
    /** Smoothly transition from position A to B with constant acceleration.
     * The yaw angle will be the same as the road at the end of the trajectory.
     * @param intention The intention of this trajectory, propagated to each coordinate.
     * @param targetLane The ultimate target lane of this trajectory. Note, this is only propagated and does not change the coordinates of the trajectory.
     * @param start Ego vehicle state at start of this trajectory.
     * @param delta_s The longitudinal change to apply in this trajectory.
     * @param delta_d The lateral change to apply in this trajectory.
     * @param delta_speed The speed change to apply in this trajectory.
     */
    Trajectory AdjustSpeed(Logic::Intention intention, int targetLane, const VehicleData::EgoVehicleData &start, double delta_s, double delta_d, double delta_speed);
  }; /* namespace TrajectoryCalculator */
}; /* namespace Path */

#endif /* TRAJECTORY_H */
