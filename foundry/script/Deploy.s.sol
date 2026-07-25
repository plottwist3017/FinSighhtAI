// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Script, console} from "forge-std/Script.sol";
import {SpendSenseMemory} from "../src/SpendSenseMemory.sol";

contract DeploySpendSenseMemory is Script {
    function run() external {
        vm.startBroadcast();

        SpendSenseMemory memory_contract = new SpendSenseMemory();

        console.log("===========================================");
        console.log("  SpendSenseMemory deployed successfully");
        console.log("===========================================");
        console.log("  Contract address:", address(memory_contract));
        console.log("  Chain ID:        ", block.chainid);
        console.log("===========================================");

        vm.stopBroadcast();
    }
}
