import json

def two_sum(nums, target):
    """
    Finds two indices in an array that sum up to a target value using a hash map.

    Args:
        nums (list[int]): The input array of integers.
        target (int): The target sum.

    Returns:
        list[int]: A list containing the indices of the two numbers that sum to the target.
                   Returns an empty list if no solution is found (though problem guarantees one).
    """
    num_map = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in num_map:
            return [num_map[complement], i]
        num_map[num] = i
    return [] # Should not reach here given problem constraints

def main():
    """
    Parses input from stdin, solves the Two Sum problem, and prints the result as JSON.
    """
    try:
        # Read the entire input line, assuming it's a JSON string
        input_line = input()
        input_data = json.loads(input_line)
        
        nums = input_data['nums']
        target = input_data['target']
        
        result_indices = two_sum(nums, target)
        
        # Format the output as JSON
        output = {
            "indices": result_indices
        }
        print(json.dumps(output))
        
    except KeyError as e:
        print(json.dumps({"error": f"Missing key in input JSON: {e}"}))
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON format for input."}))
    except Exception as e:
        print(json.dumps({"error": f"An unexpected error occurred: {e}"}))

if __name__ == "__main__":
    main()
