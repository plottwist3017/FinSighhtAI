// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title SpendSenseMemory
/// @notice Stores hashed financial memory snapshots on-chain.
/// @dev    No raw financial data is ever stored — only SHA-256 hashes.
contract SpendSenseMemory {
    struct Snapshot {
        bytes32 snapshotHash;
        string  month;
        uint256 timestamp;
    }

    // wallet address => list of that wallet's snapshots
    mapping(address => Snapshot[]) private snapshots;

    event SnapshotSaved(
        address indexed wallet,
        bytes32 indexed snapshotHash,
        string  month,
        uint256 timestamp
    );

    /// @notice Save a new financial memory snapshot.
    /// @param snapshotHash  SHA-256 hash of the snapshot text (as bytes32)
    /// @param month         Human-readable month label, e.g. "July 2026"
    function saveSnapshot(bytes32 snapshotHash, string calldata month) external {
        snapshots[msg.sender].push(Snapshot({
            snapshotHash: snapshotHash,
            month:        month,
            timestamp:    block.timestamp
        }));
        emit SnapshotSaved(msg.sender, snapshotHash, month, block.timestamp);
    }

    /// @notice Return all snapshots belonging to the caller.
    /// @return hashes      Array of SHA-256 hashes
    /// @return months      Array of month labels
    /// @return timestamps  Array of block timestamps
    function getSnapshots()
        external
        view
        returns (
            bytes32[] memory hashes,
            string[]  memory months,
            uint256[] memory timestamps
        )
    {
        Snapshot[] storage snaps = snapshots[msg.sender];
        uint256 len = snaps.length;
        hashes     = new bytes32[](len);
        months     = new string[](len);
        timestamps = new uint256[](len);
        for (uint256 i = 0; i < len; i++) {
            hashes[i]     = snaps[i].snapshotHash;
            months[i]     = snaps[i].month;
            timestamps[i] = snaps[i].timestamp;
        }
    }
}
