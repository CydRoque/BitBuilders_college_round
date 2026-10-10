"""
Unit and Integration Test Suite for Fairwork
Tests Blockchain integrity, Smart Contract Escrows, Late Penalties, and Relinquishment.
"""

import unittest
from backend.blockchain import Blockchain, Transaction, sha256_hash, compute_merkle_root
from backend.models import FreelancerProfile, CompanyProfile, Milestone, JobContract
from backend.fairwork_engine import FairworkEngine
from backend.app import app

class TestFairworkPlatform(unittest.TestCase):
    def setUp(self):
        self.engine = FairworkEngine()
        self.client = app.test_client()

    def test_blockchain_cryptography_and_consensus(self):
        bc = Blockchain(difficulty=2, load_persisted=False)
        self.assertTrue(bc.is_chain_valid())
        self.assertEqual(len(bc.chain), 1)

        # Add transaction
        bc.set_wallet_balance("0xALICE", 500.0)
        tx = Transaction("0xALICE", "0xBOB", 150.0, "TRANSFER")
        bc.add_transaction(tx)
        self.assertEqual(len(bc.pending_transactions), 1)

        # Mine block
        mined_block = bc.mine_pending_transactions(miner_address="0xVALIDATOR")
        self.assertTrue(mined_block.hash.startswith("00"))
        self.assertEqual(len(bc.chain), 2)
        self.assertTrue(bc.is_chain_valid())
        self.assertEqual(bc.get_wallet_balance("0xBOB"), 150.0)

    def test_freelancer_qualification_scoring(self):
        f = self.engine.freelancers["freelancer_alex"]
        score = f.calculate_qualification_score(["Solidity", "Rust", "Smart Contracts"])
        self.assertGreaterEqual(score["match_percentage"], 90.0)
        self.assertEqual(len(score["missing_skills"]), 0)

        # Non-matching skills
        score_low = f.calculate_qualification_score(["Swift", "iOS", "Kotlin", "Android"])
        self.assertLess(score_low["match_percentage"], 60.0)

    def test_milestone_on_time_full_payout(self):
        job_id = "FWK-CONTRACT-101"
        alex = self.engine.freelancers["freelancer_alex"]
        initial_balance = self.engine.blockchain.get_wallet_balance(alex.wallet_address)

        # Submit on-time
        res = self.engine.submit_deliverable(job_id, 0, alex.id, "Verified smart contract code v1.0")
        self.assertFalse(res["is_late"])
        self.assertEqual(res["delay_hours"], 0.0)
        self.assertEqual(len(res["deliverable_hash"]), 64)

        # Approve
        appr = self.engine.approve_milestone(job_id, 0, "company_novatech")
        self.assertEqual(appr["payout"], 2000.0)
        self.assertEqual(appr["penalty"], 0.0)
        self.assertEqual(appr["refund"], 0.0)

        new_balance = self.engine.blockchain.get_wallet_balance(alex.wallet_address)
        self.assertEqual(new_balance, initial_balance + 2000.0)

    def test_milestone_deadline_penalty_calculation(self):
        job_id = "FWK-CONTRACT-101"
        alex = self.engine.freelancers["freelancer_alex"]
        comp = self.engine.companies["company_novatech"]
        init_comp_balance = self.engine.blockchain.get_wallet_balance(comp.wallet_address)

        # Advance virtual time by 30 hours (deadline is 24h, buffer is 12h, so 6h late)
        self.engine.advance_virtual_time(30)
        res = self.engine.submit_deliverable(job_id, 0, alex.id, "Delayed milestone delivery")
        self.assertTrue(res["is_late"])
        self.assertGreater(res["delay_hours"], 0.0)

        appr = self.engine.approve_milestone(job_id, 0, "company_novatech")
        self.assertGreater(appr["penalty"], 0.0)
        self.assertEqual(appr["payout"] + appr["refund"], 2000.0)

        # Company received penalty refund on-chain
        new_comp_balance = self.engine.blockchain.get_wallet_balance(comp.wallet_address)
        self.assertGreater(new_comp_balance, init_comp_balance)

    def test_relinquishment_and_fair_reassignment(self):
        job_id = "FWK-CONTRACT-101"
        alex = self.engine.freelancers["freelancer_alex"]
        priya = self.engine.freelancers["freelancer_priya"]

        # 1. Complete milestone 0 on-time for Alex
        self.engine.submit_deliverable(job_id, 0, alex.id, "Phase 1 delivered")
        self.engine.approve_milestone(job_id, 0, "company_novatech")
        alex_settled_balance = self.engine.blockchain.get_wallet_balance(alex.wallet_address)

        # 2. Advance time beyond buffer for milestone 1 (deadline 36h + buffer 18h = 54h; advance 70h)
        self.engine.advance_virtual_time(70)

        # 3. Trigger Fairwork Relinquishment & Reassignment
        relinq = self.engine.relinquish_and_reassign(
            job_id=job_id,
            milestone_index=1,
            reason="Buffer timeout exceeded",
            new_freelancer_id=priya.id
        )

        self.assertTrue(relinq["success"])
        self.assertEqual(relinq["new_freelancer"], priya.name)

        # Contract state verified
        contract = self.engine.contracts[job_id]
        self.assertEqual(contract.current_freelancer_id, priya.id)
        self.assertEqual(contract.milestones[1].status, "IN_PROGRESS")
        self.assertEqual(contract.milestones[1].assigned_freelancer_id, priya.id)

        # Crucial fairness check: Alex's paid balance from milestone 0 was NOT touched or revoked!
        self.assertEqual(self.engine.blockchain.get_wallet_balance(alex.wallet_address), alex_settled_balance)

    def test_api_endpoints(self):
        # GET /api/overview
        res = self.client.get('/api/overview')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["is_chain_valid"])
        self.assertGreaterEqual(data["block_height"], 1)

        # GET /api/contracts
        res_c = self.client.get('/api/contracts')
        self.assertEqual(res_c.status_code, 200)
        self.assertIn("contracts", res_c.get_json())

    def test_session_authentication_and_role_portals(self):
        # 1. Unauthenticated root access redirects to /login
        res_root = self.client.get('/', follow_redirects=False)
        self.assertEqual(res_root.status_code, 302)
        self.assertIn('/login', res_root.location)

        # 2. Login as Company
        res_login_c = self.client.post('/api/auth/login', json={'user_id': 'company_novatech'})
        self.assertEqual(res_login_c.status_code, 200)
        data_c = res_login_c.get_json()
        self.assertTrue(data_c['success'])
        self.assertEqual(data_c['redirect'], '/company')

        # Company can now view company portal
        res_c_dash = self.client.get('/company')
        self.assertEqual(res_c_dash.status_code, 200)

        # Company blocked from accessing freelancer portal (redirected to /login)
        res_f_blocked = self.client.get('/freelancer', follow_redirects=False)
        self.assertEqual(res_f_blocked.status_code, 302)

        # Check /api/me
        res_me = self.client.get('/api/me')
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()['user']['role'], 'company')

        # 3. Logout
        res_logout = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(res_logout.status_code, 302)

        # 4. Login as Freelancer
        res_login_f = self.client.post('/api/auth/login', json={'user_id': 'freelancer_alex'})
        self.assertEqual(res_login_f.status_code, 200)
        data_f = res_login_f.get_json()
        self.assertTrue(data_f['success'])
        self.assertEqual(data_f['redirect'], '/freelancer')

        # Freelancer can view freelancer portal
        res_f_dash = self.client.get('/freelancer')
        self.assertEqual(res_f_dash.status_code, 200)

    def test_whatsapp_chat_messaging_and_image_storage(self):
        # 1. Login as Freelancer Alex
        self.client.post('/api/auth/login', json={'user_id': 'freelancer_alex'})

        # Send text + image message
        send_res = self.client.post('/api/chat/FWK-CONTRACT-101/send', json={
            'text': 'Here is the deployed contract screenshot and test logs.',
            'image_data': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
        })
        self.assertEqual(send_res.status_code, 201)
        new_msg = send_res.get_json()['message']
        self.assertEqual(new_msg['sender_id'], 'freelancer_alex')
        self.assertIn('data:image/png', new_msg['image_data'])

        # 2. Login as Company NovaTech and read chat
        self.client.post('/api/auth/login', json={'user_id': 'company_novatech'})
        get_res = self.client.get('/api/chat/FWK-CONTRACT-101')
        self.assertEqual(get_res.status_code, 200)
        messages = get_res.get_json()['messages']
        self.assertGreaterEqual(len(messages), 4)

        # Company replies with text
        reply_res = self.client.post('/api/chat/FWK-CONTRACT-101/send', json={
            'text': 'Image received! Code verified on block explorer.'
        })
        self.assertEqual(reply_res.status_code, 201)

if __name__ == "__main__":
    unittest.main()


