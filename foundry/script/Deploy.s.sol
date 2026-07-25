// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script, console} from "forge-std/Script.sol";
import {FinSightAI} from "../src/FinSightAI.sol";

contract DeployFinSightAI is Script {
    function run() external {
        vm.startBroadcast();

        FinSightAI memory_contract = new FinSightAI();

        console.log("===========================================");
        console.log("  FinSight AI deployed successfully");
        console.log("  Built using IBM Bob - Made by Kavya Raval");
        console.log("===========================================");
        console.log("  Contract address:", address(memory_contract));
        console.log("  Chain ID:        ", block.chainid);
        console.log("===========================================");

        vm.stopBroadcast();
    }
}
