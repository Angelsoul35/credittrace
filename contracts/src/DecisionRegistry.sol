// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title DecisionRegistry
/// @author Angelo David Padilla Romero
/// @notice Tamper-evident registry of credit-decision digests.
/// @dev The contract never sees applicant data. The off-chain scoring service
///      computes a keccak256 digest over the canonical decision payload
///      (features + model version + score + outcome) and anchors only that
///      32-byte digest. Anyone holding the original payload can later recompute
///      the digest and prove, against this registry, that the decision existed
///      at a given block and was not altered afterwards.
contract DecisionRegistry {
    struct Record {
        address submitter; // scorer that anchored the digest
        uint64 timestamp; // block timestamp at anchoring (0 => absent)
        uint64 blockNumber; // block number at anchoring
    }

    address public owner;
    mapping(address => bool) public isScorer;
    mapping(bytes32 => Record) private _records;

    event DecisionAnchored(
        bytes32 indexed digest, address indexed submitter, uint64 timestamp, uint64 blockNumber
    );
    event ScorerUpdated(address indexed scorer, bool allowed);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    error NotOwner();
    error NotScorer();
    error AlreadyAnchored(bytes32 digest);
    error ZeroDigest();
    error ZeroAddress();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyScorer() {
        if (!isScorer[msg.sender]) revert NotScorer();
        _;
    }

    constructor() {
        owner = msg.sender;
        isScorer[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit ScorerUpdated(msg.sender, true);
    }

    /// @notice Grant or revoke the right to anchor decisions.
    function setScorer(address scorer, bool allowed) external onlyOwner {
        if (scorer == address(0)) revert ZeroAddress();
        isScorer[scorer] = allowed;
        emit ScorerUpdated(scorer, allowed);
    }

    /// @notice Transfer ownership of the registry.
    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        address previous = owner;
        owner = newOwner;
        emit OwnershipTransferred(previous, newOwner);
    }

    /// @notice Anchor a decision digest. Each digest can be anchored once.
    /// @param digest keccak256 of the canonical decision payload.
    /// @return blockNumber the block the digest was anchored in.
    function anchor(bytes32 digest) external onlyScorer returns (uint64 blockNumber) {
        if (digest == bytes32(0)) revert ZeroDigest();
        if (_records[digest].timestamp != 0) revert AlreadyAnchored(digest);

        Record memory record = Record({
            submitter: msg.sender,
            timestamp: uint64(block.timestamp),
            blockNumber: uint64(block.number)
        });
        _records[digest] = record;

        emit DecisionAnchored(digest, msg.sender, record.timestamp, record.blockNumber);
        return record.blockNumber;
    }

    /// @notice Return the stored record for a digest (zeroed if absent).
    function recordOf(bytes32 digest)
        external
        view
        returns (address submitter, uint64 timestamp, uint64 blockNumber)
    {
        Record memory record = _records[digest];
        return (record.submitter, record.timestamp, record.blockNumber);
    }

    /// @notice Whether a digest has been anchored.
    function isAnchored(bytes32 digest) external view returns (bool) {
        return _records[digest].timestamp != 0;
    }
}
