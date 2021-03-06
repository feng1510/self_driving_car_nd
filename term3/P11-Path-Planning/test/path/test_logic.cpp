#include "../../src/constants.h"
#include "../../src/helpers.h"
#include "../../src/path/logic.h"
#include <algorithm>
#include <iostream>
#include <vector>
#include "../catch.hpp"

using namespace std;

TEST_CASE("Path logic should provide all intentions that remains on road.", "[path]") {
  // Lookup table for lanes d coordinates.
  const double dValueOfLane[] = {(constants.laneWidth / 2.0),
                                 (constants.laneWidth / 2.0) + constants.laneWidth,
                                 (constants.laneWidth / 2.0) + constants.laneWidth * 2.0};
  struct TestCase {
    double d;
    vector<Path::Logic::Intention> expectedIntentions;
  };

  vector<TestCase> testVector = {
    /* Lane 0 */
    {.d = dValueOfLane[0], .expectedIntentions = {Path::Logic::Intention::KeepLane,
                                                  Path::Logic::Intention::LaneChangeRight,
                                                  Path::Logic::Intention::PrepareLaneChangeRight,
                                                  Path::Logic::Intention::TwoLaneChangesRight,}},
    /* Lane 1 */
    {.d = dValueOfLane[1], .expectedIntentions = {Path::Logic::Intention::KeepLane,
                                                  Path::Logic::Intention::LaneChangeLeft,
                                                  Path::Logic::Intention::LaneChangeRight,
                                                  Path::Logic::Intention::PrepareLaneChangeLeft,
                                                  Path::Logic::Intention::PrepareLaneChangeRight}},
    /* Lane 2 */
    {.d = dValueOfLane[2], .expectedIntentions = {Path::Logic::Intention::KeepLane,
                                                  Path::Logic::Intention::LaneChangeLeft,
                                                  Path::Logic::Intention::PrepareLaneChangeLeft,
                                                  Path::Logic::Intention::TwoLaneChangesLeft}},
  };

  Path::Logic logic;
  for (auto testCase = testVector.begin(); testCase != testVector.end(); ++testCase) {
    vector<Path::Logic::Intention> actualIntentions = logic.GetIntentionsToEvaluate(testCase->d);
    REQUIRE(actualIntentions.size() == testCase->expectedIntentions.size());
    for (auto expected = testCase->expectedIntentions.begin(); expected != testCase->expectedIntentions.end(); ++expected) {
      REQUIRE(find(actualIntentions.begin(), actualIntentions.end(), *expected) != actualIntentions.end());
    }
  }
}
