// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script} from "forge-std/Script.sol";
import {DecisionRegistry} from "../src/DecisionRegistry.sol";

/// @notice Deploy DecisionRegistry. Set PRIVATE_KEY in the environment.
contract Deploy is Script {
    function run() external returns (DecisionRegistry registry) {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        registry = new DecisionRegistry();
        vm.stopBroadcast();
    }
}
