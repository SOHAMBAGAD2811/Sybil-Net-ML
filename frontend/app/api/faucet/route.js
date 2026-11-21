import { NextResponse } from 'next/server';
import { ethers } from 'ethers';

export async function POST(req) {
  try {
    const { address } = await req.json();
    if (!address) {
      return NextResponse.json({ error: 'Address required' }, { status: 400 });
    }

    // Connect to the local Hardhat node
    const provider = new ethers.JsonRpcProvider('http://127.0.0.1:8545');
    
    // Standard Hardhat Account #0 Private Key (pre-funded with 10,000 ETH)
    const privKey = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80';
    const wallet = new ethers.Wallet(privKey, provider);

    // Send 10 ETH to the requested address
    const tx = await wallet.sendTransaction({
      to: address,
      value: ethers.parseEther('10.0')
    });
    
    await tx.wait();

    return NextResponse.json({ success: true, hash: tx.hash });
  } catch (error) {
    console.error('Faucet error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
