// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {DecisionRegistry} from "../src/DecisionRegistry.sol";

contract DecisionRegistryTest is Test {
    DecisionRegistry internal registry;
    address internal owner = address(this);
    address internal scorer = address(0xBEEF);
    address internal outsider = address(0xCAFE);
    bytes32 internal constant DIGEST = keccak256("decision-1");

    function setUp() public {
        registry = new DecisionRegistry();
    }

    function test_OwnerIsScorerByDefault() public view {
        assertTrue(registry.isScorer(owner));
        assertEq(registry.owner(), owner);
    }

    function test_AnchorStoresRecord() public {
        registry.anchor(DIGEST);
        (address submitter, uint64 timestamp, uint64 blockNumber) = registry.recordOf(DIGEST);
        assertEq(submitter, owner);
        assertGt(timestamp, 0);
        assertEq(blockNumber, uint64(block.number));
        assertTrue(registry.isAnchored(DIGEST));
    }

    function test_EmitsDecisionAnchored() public {
        vm.expectEmit(true, true, false, false);
        emit DecisionRegistry.DecisionAnchored(DIGEST, owner, uint64(block.timestamp), uint64(block.number));
        registry.anchor(DIGEST);
    }

    function test_RevertWhen_AnchoredTwice() public {
        registry.anchor(DIGEST);
        vm.expectRevert(abi.encodeWithSelector(DecisionRegistry.AlreadyAnchored.selector, DIGEST));
        registry.anchor(DIGEST);
    }

    function test_RevertWhen_NotScorer() public {
        vm.prank(outsider);
        vm.expectRevert(DecisionRegistry.NotScorer.selector);
        registry.anchor(DIGEST);
    }

    function test_RevertWhen_ZeroDigest() public {
        vm.expectRevert(DecisionRegistry.ZeroDigest.selector);
        registry.anchor(bytes32(0));
    }

    function test_SetScorerGrantsAccess() public {
        registry.setScorer(scorer, true);
        vm.prank(scorer);
        registry.anchor(DIGEST);
        assertTrue(registry.isAnchored(DIGEST));
    }

    function test_RevertWhen_SetScorerNotOwner() public {
        vm.prank(outsider);
        vm.expectRevert(DecisionRegistry.NotOwner.selector);
        registry.setScorer(scorer, true);
    }

    function test_TransferOwnership() public {
        registry.transferOwnership(scorer);
        assertEq(registry.owner(), scorer);
    }

    function testFuzz_AnchorArbitraryNonZeroDigest(bytes32 digest) public {
        vm.assume(digest != bytes32(0));
        registry.anchor(digest);
        assertTrue(registry.isAnchored(digest));
    }
}
