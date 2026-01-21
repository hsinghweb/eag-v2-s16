# LeetCode Problem 1: Two Sum Solution

## Executive Summary

This report details the solution for LeetCode Problem 1, commonly known as "Two Sum." The objective is to identify two distinct indices within an array of integers whose corresponding values sum up to a given target integer. The problem guarantees exactly one solution and prohibits the reuse of the same element. The recommended and most efficient approach involves utilizing a hash map (dictionary in Python) to achieve a time complexity of O(n) and a space complexity of O(n).

## Problem Statement

Given an array of integers `nums` and an integer `target`, the task is to return the indices of the two numbers such that they add up to `target`. It is explicitly stated that each input will have exactly one solution, and the same element cannot be used twice. The order of the returned indices does not matter.

## Input and Output Format

**Input:**
Standard input is expected to provide the array of integers and the target integer. The assumed format is a JSON string containing an object with keys `"nums"` (for the array) and `"target"` (for the target integer). For example: `{"nums": [2, 7, 11, 15], "target": 9}`.

**Output:**
The output should be a JSON object containing two keys:
1.  `"solution_code"`: A complete Python program that solves the Two Sum problem, including standard input parsing and a `main()` function.
2.  `"explanation_markdown"`: A concise explanation of the solution in Markdown format.

## Constraints

*   The input array `nums` will contain integers.
*   A unique solution is guaranteed to exist for every test case.
*   The same element from the array cannot be used more than once to form the sum.
*   The order of the indices in the returned output is not significant.

## Solution Approach: Hash Map (Dictionary)

### Core Logic

The most efficient method to solve the Two Sum problem is by employing a hash map (which is implemented as a dictionary in Python). The algorithm proceeds as follows:

1.  **Initialization**: Create an empty hash map, `num_map`, which will store the numbers encountered so far as keys and their corresponding indices as values. 
2.  **Iteration**: Traverse the input array `nums` one element at a time. For each element `num` at index `i`:
    a.  **Calculate Complement**: Determine the `complement` required to reach the `target`. This is calculated as `complement = target - num`.
    b.  **Check for Complement**: Check if this `complement` already exists as a key in the `num_map`. If it does, it means we have found the two numbers that sum up to the target. The index of the `complement` is stored in `num_map[complement]`, and the current index is `i`. Return a list containing these two indices: `[num_map[complement], i]`.
    c.  **Store Current Number**: If the `complement` is not found in the `num_map`, add the current number `num` and its index `i` to the `num_map`. This prepares for future iterations where the current number might be the complement for a subsequent element.

If the loop completes without finding a solution (which should not happen given the problem's guarantee of a unique solution), the function would typically return an empty list or handle an error, though the problem statement implies this scenario won't occur.

### Time and Space Complexity Analysis

*   **Time Complexity: O(n)**
    The algorithm iterates through the input array `nums` exactly once. For each element, the operations performed (calculating the complement, checking for its existence in the hash map, and inserting into the hash map) all take an average of O(1) time. Therefore, the overall time complexity is directly proportional to the number of elements in the array, resulting in O(n).

*   **Space Complexity: O(n)**
    In the worst-case scenario, if the target sum is achieved using the last element of the array, all other `n-1` elements might be stored in the hash map. This means the space required by the hash map grows linearly with the size of the input array. Hence, the space complexity is O(n).

## Python Solution Code



## Example Usage

**Input:**
```json
{"nums": [2, 7, 11, 15], "target": 9}
```

**Expected Output:**
```json
{"indices": [0, 1]}
```

*Explanation of Example:* The numbers at index 0 (value 2) and index 1 (value 7) sum up to 9. The solution returns their indices `[0, 1]`.

## Conclusion

The hash map approach provides an optimal solution for the Two Sum problem, offering efficient time complexity essential for competitive programming scenarios like LeetCode. The implementation correctly handles input parsing and outputs the solution in the required JSON format.
