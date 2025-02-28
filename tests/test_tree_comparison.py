import pytest
from weiroll import Planner, Contract, Decoder, CallType

# Test that the decoded plan tree outputs the same structure as the original plan tree
def test_decoded_tree_matches_original():
    """Test that the decoded plan tree matches the structure of the original plan tree."""
    # Create a mock contract adapter for testing
    class MockContract:
        def __init__(self, address, name="MockContract"):
            self.address = address
            self.name = name
            self.abi = [
                {
                    'inputs': [{'type': 'address'}, {'type': 'uint256'}],
                    'name': 'approve',
                    'outputs': [{'type': 'bool'}],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                },
                {
                    'inputs': [{'type': 'uint256'}],
                    'name': 'deposit',
                    'outputs': [{'type': 'uint256'}],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                },
                {
                    'inputs': [{'type': 'uint256'}],
                    'name': 'stake',
                    'outputs': [],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                }
            ]
    
    # Create contracts similar to the demo
    token = Contract.create_contract(MockContract("0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI"))
    vault = Contract.create_contract(MockContract("0x19D3364A399d251E894aC732651be8B0E4e85001", "Vault"))
    
    # Create a planner with operations
    planner = Planner()
    
    # Amount to deposit (1000 DAI with 18 decimals)
    amount = 1000 * 10**18
    
    # Create a plan similar to the demo
    approval = planner.add(token.approve(vault.address, amount))
    shares = planner.add(vault.deposit(amount))
    
    # Generate the encoded plan
    plan = planner.plan()
    
    # Get the original plan tree as a string
    original_tree = planner.show_tree()
    
    # Decode the plan
    decoded_plan = Decoder.decode_plan(plan["commands"], plan["state"])
    
    # Get the decoded plan tree as a string
    decoded_tree = decoded_plan.show_tree()
    
    # Compare the essential structure (ignoring formatting differences)
    # Print the trees for debugging
    print("Original tree:")
    print(original_tree)
    print("\nDecoded tree:")
    print(decoded_tree)
    
    # Step 1: Check that both have the same number of commands
    assert len(planner.commands) == len(decoded_plan.commands)
    
    # Step 2: Check that both trees have the same command structure
    # We'll look for key indicators in each string
    
    # Both should have the same number of "Command N:" occurrences
    assert original_tree.count("Command") == decoded_tree.count("Command")
    
    # Both should have the same number of input states
    assert original_tree.count("Input") == decoded_tree.count("Input")
    
    # Both should have the same number of outputs
    assert original_tree.count("Output") == decoded_tree.count("Output")
    
    # Both should have the same data flow references (from Command X output)
    assert original_tree.count("from Command") == decoded_tree.count("from Command")
    
    # Check that the target addresses are preserved (case-insensitive)
    assert "0x6B175474".lower() in original_tree.lower() and "0x6B175474".lower() in decoded_tree.lower()
    assert "0x19D3364A".lower() in original_tree.lower() and "0x19D3364A".lower() in decoded_tree.lower()
    
    # You can add more detailed comparisons as needed
    
    
def test_roundtrip_reconstructed_planner():
    """Test that a reconstructed planner from a decoded plan produces the same structure."""
    # Create a mock contract adapter for testing
    class MockContract:
        def __init__(self, address, name="MockContract"):
            self.address = address
            self.name = name
            self.abi = [
                {
                    'inputs': [{'type': 'address'}, {'type': 'uint256'}],
                    'name': 'approve',
                    'outputs': [{'type': 'bool'}],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                },
                {
                    'inputs': [{'type': 'uint256'}],
                    'name': 'deposit',
                    'outputs': [{'type': 'uint256'}],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                },
                {
                    'inputs': [{'type': 'uint256'}],
                    'name': 'stake',
                    'outputs': [],
                    'stateMutability': 'nonpayable',
                    'type': 'function'
                }
            ]
    
    # Create contracts similar to the demo
    token = Contract.create_contract(MockContract("0x6B175474E89094C44Da98b954EedeAC495271d0F", "DAI"))
    vault = Contract.create_contract(MockContract("0x19D3364A399d251E894aC732651be8B0E4e85001", "Vault"))
    
    # Create a planner with operations
    original_planner = Planner()
    
    # Amount to deposit (1000 DAI with 18 decimals)
    amount = 1000 * 10**18
    
    # Create a plan similar to the demo
    approval = original_planner.add(token.approve(vault.address, amount))
    shares = original_planner.add(vault.deposit(amount))
    
    # Generate the encoded plan
    original_plan = original_planner.plan()
    
    # Decode the plan
    decoded_plan = Decoder.decode_plan(original_plan["commands"], original_plan["state"])
    
    # Reconstruct a planner from the decoded plan
    reconstructed_planner = Decoder.to_planner(decoded_plan)
    
    # Generate a new plan from the reconstructed planner
    reconstructed_plan = reconstructed_planner.plan()
    
    # Compare structure
    assert len(original_plan["commands"]) == len(reconstructed_plan["commands"])
    assert len(reconstructed_planner.commands) == len(original_planner.commands)
    
    # Check if command types are preserved
    for i in range(len(original_planner.commands)):
        original_cmd = original_planner.commands[i]
        reconstructed_cmd = reconstructed_planner.commands[i]
        
        # Check that call types match
        assert original_cmd.call_type == reconstructed_cmd.call_type
        
        # Check that targets match
        assert bytes(original_cmd.target) == bytes(reconstructed_cmd.target)
        
        # Check that selectors match
        assert bytes(original_cmd.function_selector) == bytes(reconstructed_cmd.function_selector)
        
        # Check that input and output structure matches
        assert len(original_cmd.inputs) == len(reconstructed_cmd.inputs)
        assert (original_cmd.output is None) == (reconstructed_cmd.output is None)