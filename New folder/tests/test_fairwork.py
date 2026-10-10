"""
Unit and Integration Test Suite for Fairwork
Tests Blockchain integrity, Smart Contract Escrows, Late Penalties, and Relinquishment.
"""

import unittest
import json
import tempfile
from unittest.mock import patch
from backend.blockchain import Blockchain, Transaction, sha256_hash, compute_merkle_root
from backend.models import FreelancerProfile, CompanyProfile, Milestone, JobContract
from backend.fairwork_engine import FairworkEngine
from backend.app import app, chat_store
from backend.auth_store import AuthStore
import backend.app as app_module


def demo_login(client, username):
    return client.post("/api/auth/login", json={
        "username": username,
        "password": "demo12345"
    })


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

    def test_deliverable_api_requires_assigned_freelancer_and_content(self):
        with patch.object(app_module, "engine", self.engine), \
                patch("backend.db.DatabaseService.save_block_and_transactions"), \
                patch("backend.db.DatabaseService.save_wallet_balance"), \
                patch("backend.db.DatabaseService.save_contract"):
            anonymous = app.test_client()
            self.assertEqual(
                anonymous.post("/api/contracts/FWK-CONTRACT-101/submit_deliverable", json={
                    "milestone_index": 0,
                    "deliverable_text": "Finished"
                }).status_code,
                401
            )

            company = app.test_client()
            demo_login(company, "company_novatech")
            self.assertEqual(
                company.post("/api/contracts/FWK-CONTRACT-101/submit_deliverable", json={
                    "milestone_index": 0,
                    "deliverable_text": "Finished"
                }).status_code,
                403
            )

            freelancer = app.test_client()
            demo_login(freelancer, "freelancer_alex")
            empty_response = freelancer.post(
                "/api/contracts/FWK-CONTRACT-101/submit_deliverable",
                json={"milestone_index": 0, "deliverable_text": " ", "deliverable_link": ""}
            )
            self.assertEqual(empty_response.status_code, 400)

            response = freelancer.post(
                "/api/contracts/FWK-CONTRACT-101/submit_deliverable",
                json={"milestone_index": 0, "deliverable_text": "Verified deliverable"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["success"])
            self.assertEqual(
                self.engine.contracts["FWK-CONTRACT-101"].milestones[0].status,
                "SUBMITTED"
            )

    def test_company_handoff_requires_a_different_replacement_freelancer(self):
        with patch.object(app_module, "engine", self.engine), \
                patch("backend.db.DatabaseService.save_block_and_transactions"), \
                patch("backend.db.DatabaseService.save_wallet_balance"), \
                patch("backend.db.DatabaseService.save_contract"):
            company = app.test_client()
            demo_login(company, "company_novatech")
            url = "/api/contracts/FWK-CONTRACT-101/relinquish"

            same_freelancer = company.post(url, json={
                "milestone_index": 0,
                "reason": "Reassign task",
                "new_freelancer_id": "freelancer_alex"
            })
            self.assertEqual(same_freelancer.status_code, 400)

            response = company.post(url, json={
                "milestone_index": 0,
                "reason": "Reassign remaining work",
                "new_freelancer_id": "freelancer_priya"
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["result"]["new_freelancer"], "Priya Sharma")
            self.assertEqual(
                self.engine.contracts["FWK-CONTRACT-101"].current_freelancer_id,
                "freelancer_priya"
            )
            updated_contract = company.get("/api/contract/FWK-CONTRACT-101").get_json()["contract"]
            self.assertEqual(updated_contract["current_freelancer_id"], "freelancer_priya")
            self.assertEqual(updated_contract["freelancer_name"], "Priya Sharma")

    def test_company_can_accept_an_applicant_for_its_open_contract(self):
        contract = self.engine.contracts["FWK-CONTRACT-101"]
        contract.status = "OPEN"
        contract.current_freelancer_id = None
        contract.milestones[0].status = "PENDING"
        contract.milestones[0].assigned_freelancer_id = None
        with patch.object(app_module, "engine", self.engine), \
                patch("backend.db.DatabaseService.save_block_and_transactions"), \
                patch("backend.db.DatabaseService.save_wallet_balance"), \
                patch("backend.db.DatabaseService.save_contract"):
            company = app.test_client()
            demo_login(company, "company_novatech")
            response = company.post(
                "/api/contracts/FWK-CONTRACT-101/allot",
                json={"freelancer_id": "freelancer_priya"}
            )
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
            self.assertTrue(result["success"])
            self.assertEqual(result["freelancer_name"], "Priya Sharma")
            self.assertEqual(result["contract"]["current_freelancer_id"], "freelancer_priya")
            self.assertEqual(result["contract"]["milestones"][0]["status"], "IN_PROGRESS")

    def test_company_cannot_accept_for_another_company_or_a_non_applicant(self):
        contract = self.engine.contracts["FWK-CONTRACT-101"]
        contract.status = "OPEN"
        with patch.object(app_module, "engine", self.engine):
            anonymous = app.test_client()
            self.assertEqual(
                anonymous.post(
                    "/api/contracts/FWK-CONTRACT-101/allot",
                    json={"freelancer_id": "freelancer_priya"}
                ).status_code,
                401
            )
            other_company = app.test_client()
            demo_login(other_company, "company_aurora")
            self.assertEqual(
                other_company.post(
                    "/api/contracts/FWK-CONTRACT-101/allot",
                    json={"freelancer_id": "freelancer_priya"}
                ).status_code,
                403
            )
            company = app.test_client()
            demo_login(company, "company_novatech")
            self.assertEqual(
                company.post(
                    "/api/contracts/FWK-CONTRACT-101/allot",
                    json={"freelancer_id": "freelancer_marcus"}
                ).status_code,
                400
            )

    def test_engine_clock_reads_current_wall_time(self):
        with patch("backend.fairwork_engine.time.time", return_value=1_800_000_000):
            first_time = self.engine.get_virtual_time()
        with patch("backend.fairwork_engine.time.time", return_value=1_800_000_005):
            later_time = self.engine.get_virtual_time()
        self.assertEqual(later_time - first_time, 5)

    def test_time_travel_api_is_disabled(self):
        with patch.object(app_module, "engine", self.engine):
            advance_response = self.client.post("/api/time/advance", json={"hours": 24})
            reset_response = self.client.post("/api/time/reset")
        self.assertEqual(advance_response.status_code, 410)
        self.assertEqual(reset_response.status_code, 410)
        self.assertFalse(advance_response.get_json()["success"])
        self.assertFalse(reset_response.get_json()["success"])

    def test_company_and_freelancer_dashboards_label_balances_in_usdc(self):
        with patch.object(app_module, "engine", self.engine):
            company = app.test_client()
            demo_login(company, "company_novatech")
            company_page = company.get("/company")
            self.assertEqual(company_page.status_code, 200)
            self.assertIn(b"USDC", company_page.data)
            self.assertIn(b"Local Time:", company_page.data)
            self.assertIn(b"setInterval(refreshData, 3000)", company_page.data)
            self.assertIn(b"function showToast(message, type = 'success')", company_page.data)
            self.assertIn(b"Accept Freelancer", company_page.data)
            self.assertNotRegex(
                company_page.get_data(as_text=True),
                r"\d[\d,]*(?:\.\d+)?\s+FWK\b"
            )

            freelancer = app.test_client()
            demo_login(freelancer, "freelancer_alex")
            freelancer_page = freelancer.get("/freelancer")
            self.assertEqual(freelancer_page.status_code, 200)
            self.assertIn(b"USDC", freelancer_page.data)
            self.assertIn(b"Local Time:", freelancer_page.data)
            self.assertIn(b"setInterval(refreshData, 3000)", freelancer_page.data)
            self.assertIn(b"current_freelancer_id === currentUserId", freelancer_page.data)
            self.assertNotRegex(
                freelancer_page.get_data(as_text=True),
                r"\d[\d,]*(?:\.\d+)?\s+FWK\b"
            )

    def test_api_endpoints(self):
        # GET /api/overview
        res = self.client.get('/api/overview')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["is_chain_valid"])
        self.assertGreaterEqual(data["block_height"], 1)
        self.assertIn("current_time", data)
        self.assertIn("current_time_str", data)

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
        res_login_c = demo_login(self.client, "company_novatech")
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
        res_login_f = demo_login(self.client, "freelancer_alex")
        self.assertEqual(res_login_f.status_code, 200)
        data_f = res_login_f.get_json()
        self.assertTrue(data_f['success'])
        self.assertEqual(data_f['redirect'], '/freelancer')

        # Freelancer can view freelancer portal
        res_f_dash = self.client.get('/freelancer')
        self.assertEqual(res_f_dash.status_code, 200)

    def test_login_page_includes_existing_signin_and_translate_widget(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('id="view-signin"', page)
        self.assertIn('id="signin-password"', page)
        self.assertIn('id="reg-username"', page)
        self.assertIn('id="reg-password"', page)
        self.assertIn("function selectDemo(username)", page)
        self.assertIn("function handleSignin(event)", page)
        self.assertIn('id="auth-feedback"', page)
        self.assertIn('id="google_translate_element"', page)
        self.assertIn("translate.google.com/translate_a/element.js", page)

    def test_login_requires_username_and_password(self):
        missing_username = self.client.post("/api/auth/login", json={
            "password": "demo12345"
        })
        self.assertEqual(missing_username.status_code, 400)

        missing_password = self.client.post("/api/auth/login", json={
            "username": "company_novatech"
        })
        self.assertEqual(missing_password.status_code, 400)

        wrong_password = self.client.post("/api/auth/login", json={
            "username": "company_novatech",
            "password": "incorrect-password"
        })
        self.assertEqual(wrong_password.status_code, 401)

        successful_login = demo_login(self.client, "company_novatech")
        self.assertEqual(successful_login.status_code, 200)
        self.assertEqual(successful_login.get_json()["user_id"], "company_novatech")

    def test_live_chat_pages_include_google_translate(self):
        for username, dashboard in (
            ("company_novatech", "/company"),
            ("freelancer_alex", "/freelancer")
        ):
            client = app.test_client()
            self.assertEqual(demo_login(client, username).status_code, 200)
            response = client.get(dashboard)
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            self.assertIn('id="chat-translate-toggle"', page)
            self.assertIn('id="chat-google-translate"', page)
            self.assertIn("/static/google_translate.js", page)

    def test_registration_persists_hashed_credentials_and_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            store_path = f"{directory}/accounts.json"
            store = AuthStore(store_path)
            payload = {
                "role": "freelancer",
                "name": "Test Freelancer",
                "username": "New.Freelancer",
                "password": "secure-pass-123",
                "skills": "Python, Flask"
            }
            with patch.object(app_module, "auth_store", store), \
                    patch.object(app_module, "engine", self.engine), \
                    patch("backend.db.DatabaseService.save_wallet_balance"):
                response = self.client.post("/api/auth/register", json=payload)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json()["username"], "New.Freelancer")

                duplicate = self.client.post("/api/auth/register", json={
                    **payload,
                    "role": "company"
                })
                self.assertEqual(duplicate.status_code, 409)

                with open(store_path, encoding="utf-8") as account_file:
                    account_data = account_file.read()
                self.assertNotIn(payload["password"], account_data)
                account_record = json.loads(account_data)["new.freelancer"]
                self.assertIn("password_hash", account_record)
                self.assertTrue(
                    AuthStore(store_path).authenticate(
                        payload["username"],
                        payload["password"]
                    )
                )

                successful_login = self.client.post("/api/auth/login", json={
                    "username": payload["username"],
                    "password": payload["password"]
                })
                self.assertEqual(successful_login.status_code, 200)
                self.assertEqual(successful_login.get_json()["user_id"], "freelancer_new.freelancer")

                failed_login = self.client.post("/api/auth/login", json={
                    "username": payload["username"],
                    "password": "wrong-password"
                })
                self.assertEqual(failed_login.status_code, 401)

    def test_whatsapp_chat_messaging_and_image_storage(self):
        # 1. Login as Freelancer Alex
        demo_login(self.client, "freelancer_alex")

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
        demo_login(self.client, "company_novatech")
        get_res = self.client.get('/api/chat/FWK-CONTRACT-101')
        self.assertEqual(get_res.status_code, 200)
        messages = get_res.get_json()['messages']
        self.assertGreaterEqual(len(messages), 4)

        # Company replies with text
        reply_res = self.client.post('/api/chat/FWK-CONTRACT-101/send', json={
            'text': 'Image received! Code verified on block explorer.'
        })
        self.assertEqual(reply_res.status_code, 201)

    def test_public_and_private_chat_rooms_are_access_controlled(self):
        original_rooms = chat_store.rooms
        original_messages = chat_store.messages
        chat_store.rooms = []
        chat_store.messages = []
        try:
            with patch.object(chat_store, "save_rooms"), \
                    patch.object(chat_store, "save_messages"), \
                    patch("backend.db.DatabaseService.save_chat_message"):
                anonymous = app.test_client()
                self.assertEqual(anonymous.get("/api/chat/rooms").status_code, 401)

                company = app.test_client()
                demo_login(company, "company_novatech")
                private_response = company.post("/api/chat/rooms", json={
                    "name": "Project Planning",
                    "visibility": "private",
                    "member_ids": ["freelancer_alex"]
                })
                self.assertEqual(private_response.status_code, 201)
                private_room = private_response.get_json()["room"]
                self.assertEqual(
                    company.get(f"/api/chat/rooms/{private_room['id']}").status_code,
                    200
                )

                alex = app.test_client()
                demo_login(alex, "freelancer_alex")
                self.assertEqual(
                    alex.get(f"/api/chat/rooms/{private_room['id']}").status_code,
                    200
                )

                priya = app.test_client()
                demo_login(priya, "freelancer_priya")
                self.assertEqual(
                    priya.get(f"/api/chat/rooms/{private_room['id']}").status_code,
                    404
                )
                visible_private_rooms = priya.get("/api/chat/rooms").get_json()["rooms"]
                self.assertNotIn(private_room["id"], [room["id"] for room in visible_private_rooms])

                public_response = alex.post("/api/chat/rooms", json={
                    "name": "Freelancer Lounge",
                    "visibility": "public"
                })
                self.assertEqual(public_response.status_code, 201)
                public_room = public_response.get_json()["room"]
                send_response = alex.post(
                    f"/api/chat/rooms/{public_room['id']}/send",
                    json={"text": "Hello, everyone!"}
                )
                self.assertEqual(send_response.status_code, 201)
                public_messages = priya.get(
                    f"/api/chat/rooms/{public_room['id']}"
                ).get_json()["messages"]
                self.assertEqual(public_messages[0]["text"], "Hello, everyone!")
        finally:
            chat_store.rooms = original_rooms
            chat_store.messages = original_messages

if __name__ == "__main__":
    unittest.main()
