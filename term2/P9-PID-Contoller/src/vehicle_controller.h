#ifndef VEHICLE_CONTROLLER_H
#define VEHICLE_CONTROLLER_H

#include <array>
#include "twiddle.h"

class VehicleController {
public:
  VehicleController();
  ~VehicleController();

  /** Available vehicle control modes. */
  enum ControlMode {
    RECOVERY = 0,
    SAFE,
    CAREFUL,
    MODERATE,
    CHALLENGING,
    BOLD,

    NUM_CONTROL_MODES,
  };
  /** Set the active vehicle control mode. */
  void SetMode(ControlMode mode);
  /** Calculate next steering value. */
  double CalcSteeringValue(double deltaTime, double speed, double cte);
  /** Calculate next throttle value. */
  double CalcThrottleValue(double deltaTime, double speed);
  /** Update the controller with next parameters to try out. */
  void SetNextParams();

private:
  struct Controller {
    double targetSpeed;
    Twiddle steering;
    Twiddle throttle;
  };

  std::array<Controller, NUM_CONTROL_MODES> controllers_;
  ControlMode currentMode_;
};

#endif /* VEHICLE_CONTROLLER_H */
