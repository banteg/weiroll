import marimo

__generated_with = "0.11.12"
app = marimo.App(width="medium")


@app.cell
def _():
    import weiroll
    from ape import chain, networks, accounts, Contract
    from pathlib import Path
    from eth_abi import encode
    from eth_utils import decode_hex, encode_hex
    from collections import defaultdict
    from rich import print
    return (
        Contract,
        Path,
        accounts,
        chain,
        decode_hex,
        defaultdict,
        encode,
        encode_hex,
        networks,
        print,
        weiroll,
    )


@app.cell
def _(Contract, print, weiroll):
    def generate_complex_plan():
        # Create contracts
        token = weiroll.Contract(Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F"))
        vault = weiroll.Contract(Contract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d"))
        farm = weiroll.Contract(Contract("0x6d225e974fa404d25ffb84ed6e242ffa18ef6430"))

        # Create planner
        planner = weiroll.Planner()

        # User address
        user = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

        amount = 1000 * 10**18

        # step 1 - get how many tokens we can deposit
        assets = planner.add(token.balanceOf(user))
        shares = planner.add(vault.deposit(assets, user))
        planner.add(vault.redeem(shares, user, user))

        return planner

    def main():
        print("Weiroll Enhanced Decoder Demo\n")

        # Generate a complex DeFi plan
        planner = generate_complex_plan()

        # Create and encode the plan
        plan = planner.plan()

        print("=== Original Plan Tree ===")
        print(planner.show_tree())
        print()

        # Decode the plan
        decoded_plan = weiroll.Decoder.decode_plan(plan["commands"], plan["state"])

        print("=== Decoded Plan Tree ===")
        print(decoded_plan)  # Uses show_tree() format by default now
        print()

        # Demonstrate converting back to a Planner
        print("=== Converting Decoded Plan back to Planner ===")
        reconstructed_planner = weiroll.Decoder.to_planner(decoded_plan)

        # Show that both plans have the same structure
        print(f"Original planner: {len(planner.commands)} commands, {len(planner.state)} state entries")
        print(f"Reconstructed planner: {len(reconstructed_planner.commands)} commands, {len(reconstructed_planner.state)} state entries")

        # Generate a new plan from the reconstructed planner 
        reconstructed_plan = reconstructed_planner.plan()
        print(f"Reconstructed plan has {len(reconstructed_plan['commands'])} commands")
    return generate_complex_plan, main


@app.cell
def _(Contract, decode_hex, encode_hex, main, networks, print):
    deposit_1 = decode_hex('0xb6b55f2500000000000000000000000000000000000000000000000000000000000003e8')
    deposit_2 = decode_hex('0x6e553f6500000000000000000000000000000000000000000000000000000000000003e8000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa96045')

    with networks.ethereum.mainnet.use_provider('http://127.0.0.1:8545'):
        main()
        token = Contract("0x6B175474E89094C44Da98b954EedeAC495271d0F")
        vault = Contract('0x19D3364A399d251E894aC732651be8B0E4e85001')
        print(vault.identifier_lookup)
        for inp in [deposit_1, deposit_2]:
            print(encode_hex(inp), 'decodes to', vault.decode_input(inp))
        # print(dir(token))
        # print(token.decode_input(
        #     decode_hex('0x095ea7b3000000000000000000000000d8da6bf26964af9d7eed9e03e53415d37aa9604500000000000000000000000000000000000000000000000000000000000003e8')))
    return deposit_1, deposit_2, inp, token, vault


@app.cell
def _(Contract, defaultdict, networks, print, weiroll):
    from ape.contracts.base import _select_method_abi

    with networks.ethereum.mainnet.use_provider('http://127.0.0.1:8545'):
        v = Contract("0xd8063123BBA3B480569244AE66BFE72B6c84b00d")
        print(v)
        # for item in v.contract_type.method_identifiers:
        #     print(item)
        #     print(v.contract_type.methods[item].inputs)
        functions = defaultdict(list)
        for item in v.contract_type.methods:
            functions[item.name].append(item.selector)

        # print(functions)
        vw = weiroll.Contract(v)
        print(vw.withdraw)
        vw_call = vw.withdraw('0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045', '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045', 1)
        print(vw_call)
        print(vw_call.selector)
        print(vw_call.target)
        # abis = _select_method_abi(v.contract_type.methods, [123])
        # print(abis)
        # print(abis.name)
    return functions, item, v, vw, vw_call


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
