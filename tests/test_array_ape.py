import pytest
from weiroll import Contract, Planner, CallType

# Import Ape components
try:
    from ape import Contract as ApeContract, accounts, project, chain
    from ape.api.address import Address
    APE_AVAILABLE = True
except ImportError:
    APE_AVAILABLE = False

# Skip tests if ape is not installed
pytestmark = pytest.mark.skipif(not APE_AVAILABLE, reason="ape is not installed")


def test_array_in_planner_with_ape_contracts(dev, ape_dai, ape_weth, ape_uniswap):
    """Test using address arrays with Weiroll planner and Ape contracts"""
    # Debug info about contracts
    print(f"DAI address: {ape_dai.address}")
    print(f"WETH address: {ape_weth.address}")
    print(f"Uniswap Router address: {ape_uniswap.address}")
    
    # Create Weiroll contract wrappers
    dai_wei = Contract.create_contract(ape_dai)
    weth_wei = Contract.create_contract(ape_weth)
    uniswap_wei = Contract.create_contract(ape_uniswap)
    
    # Create planner
    planner = Planner()
    
    # Set up swap parameters
    amount = 1000 * 10**18  # 1000 DAI
    deadline = chain.blocks[-1].timestamp + 3600  # 1 hour from now
    
    # Convert contract objects to string addresses
    path = [str(ape_dai.address), str(ape_weth.address)]
    print(f"Path array: {path}")
    print(f"Path types: {[type(x) for x in path]}")
    
    # Approve DAI for Uniswap Router
    planner.add(dai_wei.approve(ape_uniswap.address, amount))
    
    # Swap DAI for WETH
    # The problem should be in this call with the array argument
    weth_amount = planner.add(
        uniswap_wei.swapExactTokensForTokens(
            amount, 
            0,  # Min amount out
            path,  # Path array 
            dev.address,  # Recipient
            deadline
        )
    )
    
    # Transfer received WETH back to user
    planner.add(weth_wei.transfer(dev.address, weth_amount))
    
    # Try to get the plan - this was causing the error
    try:
        plan = planner.plan()
        print("Plan successful!")
        print(f"Commands: {len(plan['commands'])}")
        print(f"State: {len(plan['state'])}")
        
        # Test passes if we can generate the plan
        assert len(plan["commands"]) == 3
        assert "state" in plan
        assert len(plan["state"]) > 0
        
    except ValueError as e:
        # Print state data for debugging if it fails
        print(f"Error: {e}")
        for i, val in enumerate(planner.state):
            print(f"State[{i}]: {val} (type: {type(val)})")
        
        # Make the test fail with informative message
        pytest.fail(f"Planner.plan() failed with: {e}")


def test_array_in_planner_with_mixed_address_types(dev, ape_dai, ape_weth, ape_uniswap):
    """Test using different formats of address arrays to identify which ones work"""
    # Create Weiroll contract wrappers
    dai_wei = Contract.create_contract(ape_dai)
    uniswap_wei = Contract.create_contract(ape_uniswap)
    
    # Create planner
    planner = Planner()
    
    # Set up swap parameters
    amount = 1000 * 10**18
    deadline = chain.blocks[-1].timestamp + 3600
    
    # Test multiple ways of formatting the path array
    test_cases = [
        {
            "name": "string addresses",
            "path": [str(ape_dai.address), str(ape_weth.address)]
        },
        {
            "name": "raw addresses",
            "path": [ape_dai.address, ape_weth.address]
        },
        {
            "name": "checksum addresses",
            "path": [
                "0x6B175474E89094C44Da98b954EedeAC495271d0F", 
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            ]
        },
        {
            "name": "lowercase addresses",
            "path": [
                "0x6b175474e89094c44da98b954eedeac495271d0f", 
                "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
            ]
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\nTesting case {i+1}: {test_case['name']}")
        print(f"Path: {test_case['path']}")
        print(f"Types: {[type(x) for x in test_case['path']]}")
        
        # Create a fresh planner for each test
        test_planner = Planner()
        
        # Approve DAI
        test_planner.add(dai_wei.approve(ape_uniswap.address, amount))
        
        # Add swap operation
        test_planner.add(
            uniswap_wei.swapExactTokensForTokens(
                amount, 
                0,
                test_case['path'],
                dev.address,
                deadline
            )
        )
        
        # Try to get the plan
        try:
            plan = test_planner.plan()
            print(f"✅ Case {i+1} ({test_case['name']}) works!")
            
            # Store which format works for later reference
            working_format = test_case['name']
            working_path = test_case['path']
            
        except ValueError as e:
            print(f"❌ Case {i+1} ({test_case['name']}) fails: {e}")
            for j, val in enumerate(test_planner.state):
                print(f"  State[{j}]: {val} (type: {type(val)})")
            
            # Not failing the test here as we want to try all formats