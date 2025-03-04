# Weiroll Tree Visualization Issue Report

## Problem Description

There is a mismatch between the Weiroll planner's encoded state and the tree visualization for function call arguments. This causes confusion when the tree visualization doesn't show the expected values for function arguments.

## Root Cause

The issue is in the `_add_to_state` method in the `Planner` class. When adding function arguments, the code tried to deduplicate state values by checking if a value already exists in the state array. However, this approach can cause problems when:

1. A value returned from a previous command (a `StateValue` object) is at state index X
2. A literal argument with the same value is passed to another function
3. The literal argument gets deduplicated and also uses state index X
4. The dependency tracking system gets confused because the visualization shows the wrong dependency relationship

## Fix Implemented

We've fixed the issue by:

1. Adding a `deduplicate` parameter to the `_add_to_state` method with a default value of `True`
2. Modifying the three methods that process function arguments (`add`, `addSubplan`, and `replaceState`) to disable deduplication for function arguments:
   - Literal arguments now always get a new state index
   - `StateValue` objects (outputs from previous commands) maintain their existing indices
   
3. This ensures that each value has its own distinct state index, which allows the tree visualization to correctly show the relationship between commands.

## Test Results

Our tests confirm that the fix successfully addresses the issue:

1. The `approve` function now correctly shows the relationship between the `balanceOf` output and the `approve` amount parameter
2. Multiple dependencies in more complex scenarios are now correctly visualized

## Implementation Notes

This change slightly increases the size of the state array since deduplication is disabled for function arguments. However, this tradeoff is worthwhile for the benefit of accurate visualization.

The fix is minimally invasive and should not affect the actual execution of commands on-chain, only the way they are visualized in the debugging tools.