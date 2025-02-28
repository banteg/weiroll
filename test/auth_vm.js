const { expect } = require("chai");
const { ethers } = require("hardhat");
const weiroll = require("@weiroll/weiroll.js");

describe("AuthVM", function () {
  let owner, user1, user2;
  let testAuthVM, factory, math, authority;

  before(async () => {
    [owner, user1, user2] = await ethers.getSigners();
    
    // Deploy test contracts
    const MathContract = await ethers.getContractFactory("Math");
    const mathContract = await MathContract.deploy();
    math = weiroll.Contract.createLibrary(mathContract);
    
    // Deploy auth-enabled VM
    const TestAuthVM = await ethers.getContractFactory("TestAuthVM");
    testAuthVM = await TestAuthVM.deploy();
    
    // Deploy AuthVMFactory
    const AuthVMFactory = await ethers.getContractFactory("AuthVMFactory");
    factory = await AuthVMFactory.deploy();
    
    // Deploy TestAuthority
    const TestAuthority = await ethers.getContractFactory("TestAuthority");
    authority = await TestAuthority.deploy();
  });

  describe("Basic Authorization", function () {
    it("Should allow owner to execute commands", async function () {
      const planner = new weiroll.Planner();
      planner.add(math.add(1, 2));
      const { commands, state } = planner.plan();
      
      // Owner should be able to execute
      await expect(testAuthVM.execute(commands, state))
        .to.not.be.reverted;
    });

    it("Should not allow non-owner to execute commands", async function () {
      const planner = new weiroll.Planner();
      planner.add(math.add(1, 2));
      const { commands, state } = planner.plan();
      
      // Non-owner should not be able to execute
      await expect(testAuthVM.connect(user1).execute(commands, state))
        .to.be.revertedWith("ds-auth-unauthorized");
    });
    
    it("Should allow owner to transfer ownership", async function () {
      // Transfer ownership to user1
      await testAuthVM.setOwner(user1.address);
      
      // Verify user1 is now the owner
      expect(await testAuthVM.owner()).to.equal(user1.address);
      
      const planner = new weiroll.Planner();
      planner.add(math.add(1, 2));
      const { commands, state } = planner.plan();
      
      // User1 should now be able to execute
      await expect(testAuthVM.connect(user1).execute(commands, state))
        .to.not.be.reverted;
      
      // Original owner should no longer be able to execute
      await expect(testAuthVM.execute(commands, state))
        .to.be.revertedWith("ds-auth-unauthorized");
      
      // Transfer ownership back to owner
      await testAuthVM.connect(user1).setOwner(owner.address);
    });
  });
  
  describe("Authority-based Authorization", function () {
    it("Should support auth via DSAuthority", async function () {
      // Set up the authority
      await testAuthVM.setAuthority(authority.address);
      
      // Grant user2 access to execute function
      const executeSelector = testAuthVM.interface.getSighash("execute(bytes32[],bytes[])");
      await authority.setPermission(user2.address, testAuthVM.address, executeSelector, true);
      
      const planner = new weiroll.Planner();
      planner.add(math.add(1, 2));
      const { commands, state } = planner.plan();
      
      // User2 should now be able to execute
      await expect(testAuthVM.connect(user2).execute(commands, state))
        .to.not.be.reverted;
      
      // User1 should still not be able to execute
      await expect(testAuthVM.connect(user1).execute(commands, state))
        .to.be.revertedWith("ds-auth-unauthorized");
    });
  });
  
  describe("Factory", function () {
    it("Should allow users to create their own VM instances", async function () {
      // User1 creates a VM
      const tx = await factory.connect(user1).createVM();
      const receipt = await tx.wait();
      
      // Get VM address from event
      const vmCreatedEvent = receipt.events.find(e => e.event === "VMCreated");
      const vmAddress = vmCreatedEvent.args.vm;
      
      // Check that user1 has a VM
      expect(await factory.hasVM(user1.address)).to.be.true;
      expect(await factory.getVM(user1.address)).to.equal(vmAddress);
      
      // Instantiate the VM
      const AuthVM = await ethers.getContractFactory("AuthVM");
      const userVM = await AuthVM.attach(vmAddress);
      
      // Check that user1 is the owner
      expect(await userVM.owner()).to.equal(user1.address);
      
      // User1 should be able to execute commands on their VM
      const planner = new weiroll.Planner();
      planner.add(math.add(1, 2));
      const { commands, state } = planner.plan();
      
      await expect(userVM.connect(user1).execute(commands, state))
        .to.not.be.reverted;
        
      // Other users should not be able to use the VM
      await expect(userVM.connect(user2).execute(commands, state))
        .to.be.revertedWith("ds-auth-unauthorized");
    });
    
    it("Should revert when a user tries to create a second VM", async function () {
      await expect(factory.connect(user1).createVM())
        .to.be.revertedWith("VM already exists");
    });
    
    it("Should get or create VM", async function () {
      // User2 doesn't have a VM yet, so this should create one
      const tx = await factory.connect(user2).getOrCreateVM();
      const receipt = await tx.wait();
      
      // Get VM address from event
      const vmCreatedEvent = receipt.events.find(e => e.event === "VMCreated");
      const vmAddress = vmCreatedEvent.args.vm;
      
      // Check that user2 has a VM
      expect(await factory.hasVM(user2.address)).to.be.true;
      expect(await factory.getVM(user2.address)).to.equal(vmAddress);
      
      // Call again, should return existing VM
      const existingVMAddress = await factory.connect(user2).callStatic.getOrCreateVM();
      expect(existingVMAddress).to.equal(vmAddress);
    });
  });

  describe("Value Transfer", function () {
    it("Should allow executing with ETH value", async function () {
      // Create a new VM for this test
      const AuthVM = await ethers.getContractFactory("AuthVM");
      const valueVM = await AuthVM.deploy();
      
      // Create a plan that will send ETH to an address
      const planner = new weiroll.Planner();
      
      // Add a payable function call
      const PayableContract = await ethers.getContractFactory("Payable");
      const payable = await PayableContract.deploy();
      const payableContract = weiroll.Contract.createContract(payable);
      
      // Amount to send
      const amount = ethers.utils.parseEther("1.0");
      planner.add(payableContract.pay().withValue(amount));
      
      const { commands, state } = planner.plan();
      
      // Execute with value
      await expect(valueVM.executeWithValue(commands, state, {
        value: amount
      }))
        .to.not.be.reverted;
      
      // Check that the contract received the ETH
      expect(await ethers.provider.getBalance(payable.address)).to.equal(amount);
    });
  });
});