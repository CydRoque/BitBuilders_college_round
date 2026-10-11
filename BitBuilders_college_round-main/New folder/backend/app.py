"""
Fairwork Web Application Server
Flask REST API, session authentication, and distinct Company / Freelancer controllers.
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import time
import os
import secrets
import re
from backend.auth_store import AuthStore
from backend.fairwork_engine import FairworkEngine

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("FAIRWORK_SECRET_KEY", "fairwork_verifiable_session_secret_2026_99a8b1c2")
app.config["SESSION_COOKIE_NAME"] = "fairwork_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

engine = FairworkEngine()
auth_store = AuthStore()
DEMO_PASSWORD = "demo12345"


def _account_profile(user_id, role, name, industry="", title="", skills=None, hourly_rate=75.0):
    return {
        "user_id": user_id,
        "role": role,
        "name": name,
        "industry": industry,
        "title": title,
        "skills": skills or [],
        "hourly_rate": hourly_rate
    }


def _initialize_accounts():
    demo_accounts = [
        ("company_novatech", "company", engine.companies["company_novatech"]),
        ("company_aurora", "company", engine.companies["company_aurora"]),
        ("freelancer_alex", "freelancer", engine.freelancers["freelancer_alex"]),
        ("freelancer_priya", "freelancer", engine.freelancers["freelancer_priya"]),
        ("freelancer_marcus", "freelancer", engine.freelancers["freelancer_marcus"])
    ]
    for username, role, user in demo_accounts:
        profile = _account_profile(
            user.id,
            role,
            user.name,
            industry=getattr(user, "industry", ""),
            title=getattr(user, "title", ""),
            skills=getattr(user, "skills", []),
            hourly_rate=getattr(user, "hourly_rate", 75.0)
        )
        auth_store.ensure_account(username, DEMO_PASSWORD, profile)

    for account in auth_store.get_accounts():
        user_id = account["user_id"]
        role = account["role"]
        if engine.get_user_by_id(user_id)[0]:
            continue
        if role == "company":
            engine.register_company(
                user_id,
                account["name"],
                account.get("industry") or "Technology & Web3"
            )
        else:
            engine.register_freelancer(
                user_id,
                account["name"],
                account.get("title") or "Blockchain Developer",
                account.get("skills", []),
                float(account.get("hourly_rate", 75.0))
            )


_initialize_accounts()

# --- Auth & Session Routing ---

@app.route("/")
def index():
    if "user_id" in session:
        role = session.get("user_role")
        if role == "company":
            return redirect(url_for("company_dashboard"))
        elif role == "freelancer":
            return redirect(url_for("freelancer_dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    # If already logged in, redirect directly to role dashboard
    if "user_id" in session:
        if session.get("user_role") == "company":
            return redirect(url_for("company_dashboard"))
        elif session.get("user_role") == "freelancer":
            return redirect(url_for("freelancer_dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/company")
def company_dashboard():
    if "user_id" not in session or session.get("user_role") != "company":
        return redirect(url_for("login_page"))
    user_id = session.get("user_id")
    company = engine.companies.get(user_id)
    if not company:
        session.clear()
        return redirect(url_for("login_page"))
    return render_template("company.html", user=company.to_dict())

@app.route("/freelancer")
def freelancer_dashboard():
    if "user_id" not in session or session.get("user_role") != "freelancer":
        return redirect(url_for("login_page"))
    user_id = session.get("user_id")
    freelancer = engine.freelancers.get(user_id)
    if not freelancer:
        session.clear()
        return redirect(url_for("login_page"))
    return render_template("freelancer.html", user=freelancer.to_dict())

# --- API Authentication Endpoints ---

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A username and password are required."}), 400
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "Enter both your username and password."}), 400
    account = auth_store.authenticate(username, password)
    if not account:
        return jsonify({"error": "Invalid username or password."}), 401

    user, detected_role = engine.get_user_by_id(account["user_id"])
    if not user or detected_role != account["role"]:
        return jsonify({"error": "This account profile is unavailable. Please contact support."}), 500

    # Save to session cookie
    session.clear()
    session["user_id"] = user.id
    session["user_role"] = detected_role
    session["user_name"] = user.name

    target_redirect = "/company" if detected_role == "company" else "/freelancer"
    return jsonify({
        "success": True,
        "redirect": target_redirect,
        "user_id": user.id,
        "user_name": user.name,
        "role": detected_role
    })

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Account details are required."}), 400
    role = data.get("role")
    name = data.get("name")
    username = data.get("username")
    password = data.get("password")
    if not isinstance(role, str) or role not in {"company", "freelancer"}:
        return jsonify({"error": "Choose either a company or freelancer account."}), 400
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Name is required."}), 400
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username.strip()):
        return jsonify({"error": "Username must be 3–32 characters using letters, numbers, dots, underscores, or hyphens."}), 400
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    username = username.strip()
    name = name.strip()
    user_id = f"{role}_{username.casefold()}"
    if engine.get_user_by_id(user_id)[0]:
        return jsonify({"error": "That username is already in use."}), 409

    if role == "company":
        industry = data.get("industry", "Technology & Web3")
        industry = industry.strip() if isinstance(industry, str) else ""
        profile = _account_profile(user_id, role, name, industry=industry or "Technology & Web3")
        try:
            auth_store.create_account(username, password, profile)
            user = engine.register_company(user_id, name, profile["industry"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
    else:
        title = data.get("title", "Blockchain Developer")
        title = title.strip() if isinstance(title, str) else ""
        raw_skills = data.get("skills", "")
        skills = [skill.strip() for skill in raw_skills.split(",") if skill.strip()] if isinstance(raw_skills, str) else []
        try:
            hourly_rate = float(data.get("hourly_rate", 75.0))
        except (TypeError, ValueError):
            return jsonify({"error": "Hourly rate must be a valid number."}), 400
        if hourly_rate < 0:
            return jsonify({"error": "Hourly rate cannot be negative."}), 400
        profile = _account_profile(
            user_id,
            role,
            name,
            title=title or "Blockchain Developer",
            skills=skills,
            hourly_rate=hourly_rate
        )
        try:
            auth_store.create_account(username, password, profile)
            user = engine.register_freelancer(
                user_id,
                name,
                profile["title"],
                skills,
                hourly_rate
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409

    session.clear()
    session["user_id"] = user.id
    session["user_role"] = role
    session["user_name"] = user.name
    return jsonify({
        "success": True,
        "redirect": "/company" if role == "company" else "/freelancer",
        "user": user.to_dict(),
        "username": username
    }), 201

@app.route("/api/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401
    
    user, role = engine.get_user_by_id(user_id)
    if not user:
        return jsonify({"authenticated": False}), 401

    u_dict = user.to_dict()
    u_dict["wallet_balance"] = engine.blockchain.get_wallet_balance(user.wallet_address)
    u_dict["role"] = role
    return jsonify({
        "authenticated": True,
        "user": u_dict
    })

# --- Platform & Blockchain APIs ---

@app.route("/api/overview", methods=["GET"])
def get_overview():
    total_escrow = sum(c.escrow_locked - c.escrow_released for c in engine.contracts.values())
    total_released = sum(c.escrow_released for c in engine.contracts.values())
    chain_valid = engine.blockchain.is_chain_valid()
    current_time = engine.get_virtual_time()
    
    return jsonify({
        "current_time": current_time,
        "current_time_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(current_time)),
        "block_height": len(engine.blockchain.chain),
        "pending_tx_count": len(engine.blockchain.pending_transactions),
        "total_contracts": len(engine.contracts),
        "total_escrow_locked": round(total_escrow, 2),
        "total_funds_released": round(total_released, 2),
        "is_chain_valid": chain_valid,
        "difficulty": engine.blockchain.difficulty
    })

@app.route("/api/contracts", methods=["GET"])
def get_contracts():
    contracts_data = []
    for c in engine.contracts.values():
        c_dict = c.to_dict()
        company = engine.companies.get(c.company_id)
        freelancer = engine.freelancers.get(c.current_freelancer_id)
        c_dict["company_name"] = company.name if company else c.company_id
        c_dict["company_avatar"] = company.avatar if company else ""
        c_dict["freelancer_name"] = freelancer.name if freelancer else "Unassigned"
        c_dict["freelancer_avatar"] = freelancer.avatar if freelancer else ""
        contracts_data.append(c_dict)
    return jsonify({"contracts": contracts_data})

@app.route("/api/contract/<contract_id>", methods=["GET"])
def get_contract(contract_id):
    contract = engine.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    
    c_dict = contract.to_dict()
    company = engine.companies.get(contract.company_id)
    freelancer = engine.freelancers.get(contract.current_freelancer_id)
    c_dict["company_name"] = company.name if company else contract.company_id
    c_dict["freelancer_name"] = freelancer.name if freelancer else "Unassigned"
    c_dict["freelancer_avatar"] = freelancer.avatar if freelancer else ""
    c_dict["onchain_transactions"] = engine.blockchain.get_transactions_for_contract(contract_id)
    return jsonify({"contract": c_dict})

@app.route("/api/freelancers", methods=["GET"])
def get_freelancers():
    freelancers_list = []
    for f in engine.freelancers.values():
        f_dict = f.to_dict()
        f_dict["wallet_balance"] = engine.blockchain.get_wallet_balance(f.wallet_address)
        freelancers_list.append(f_dict)
    return jsonify({"freelancers": freelancers_list})

@app.route("/api/companies", methods=["GET"])
def get_companies():
    companies_list = []
    for c in engine.companies.values():
        c_dict = c.to_dict()
        c_dict["wallet_balance"] = engine.blockchain.get_wallet_balance(c.wallet_address)
        companies_list.append(c_dict)
    return jsonify({"companies": companies_list})

@app.route("/api/qualification_match", methods=["POST"])
def get_qualification_match():
    data = request.json or {}
    freelancer_id = data.get("freelancer_id")
    required_skills = data.get("required_skills", [])
    
    freelancer = engine.freelancers.get(freelancer_id)
    if not freelancer:
        return jsonify({"error": "Freelancer not found"}), 404
    
    match_result = freelancer.calculate_qualification_score(required_skills)
    return jsonify({
        "freelancer_id": freelancer.id,
        "freelancer_name": freelancer.name,
        "match": match_result
    })

@app.route("/api/contracts/create", methods=["POST"])
def create_contract():
    data = request.json or {}
    # Use session user if company
    company_id = session.get("user_id") if session.get("user_role") == "company" else data.get("company_id", "company_novatech")
    title = data.get("title", "Untitled Project")
    category = data.get("category", "Development")
    description = data.get("description", "")
    required_skills = data.get("required_skills", [])
    milestones = data.get("milestones", [])
    
    try:
        contract = engine.post_job(company_id, title, category, description, required_skills, milestones)
        return jsonify({"success": True, "contract": contract.to_dict()}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/apply", methods=["POST"])
def apply_contract(contract_id):
    data = request.json or {}
    # Use session user if freelancer
    freelancer_id = session.get("user_id") if session.get("user_role") == "freelancer" else data.get("freelancer_id", "freelancer_alex")
    proposal_text = data.get("proposal_text", "Ready to execute milestone deliverables with high precision.")
    
    try:
        application = engine.apply_for_job(job_id=contract_id, freelancer_id=freelancer_id, proposal_text=proposal_text)
        return jsonify({"success": True, "application": application})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/allot", methods=["POST"])
def allot_contract(contract_id):
    if not session.get("user_id"):
        return jsonify({"error": "Sign in as the contract's company to accept a freelancer."}), 401
    if session.get("user_role") != "company":
        return jsonify({"error": "Only the contract's company can accept a freelancer."}), 403
    contract = engine.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found."}), 404
    if contract.company_id != session["user_id"]:
        return jsonify({"error": "Only the company that posted this contract can accept a freelancer."}), 403
    if contract.status != "OPEN":
        return jsonify({"error": f"This contract is {contract.status.lower()} and is no longer accepting applicants."}), 409
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    freelancer_id = data.get("freelancer_id")
    if not isinstance(freelancer_id, str) or not freelancer_id:
        return jsonify({"error": "Select an applicant to accept."}), 400
    if not any(application.get("freelancer_id") == freelancer_id for application in contract.applications):
        return jsonify({"error": "This freelancer has not applied to the selected contract."}), 400

    try:
        contract = engine.allot_job(job_id=contract_id, freelancer_id=freelancer_id)
        from backend.db import DatabaseService
        DatabaseService.save_contract(contract.to_dict())
        freelancer = engine.freelancers[freelancer_id]
        return jsonify({
            "success": True,
            "contract": contract.to_dict(),
            "freelancer_name": freelancer.name
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/submit_deliverable", methods=["POST"])
def submit_deliverable(contract_id):
    if not session.get("user_id"):
        return jsonify({"error": "Sign in as the assigned freelancer to submit deliverables."}), 401
    if session.get("user_role") != "freelancer":
        return jsonify({"error": "Only freelancers can submit deliverables."}), 403

    contract = engine.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found."}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    try:
        milestone_index = int(data.get("milestone_index"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid milestone_index is required."}), 400

    deliverable_text = data.get("deliverable_text", "")
    deliverable_link = data.get("deliverable_link", "")
    if not isinstance(deliverable_text, str) or not isinstance(deliverable_link, str):
        return jsonify({"error": "Deliverable details and link must be text."}), 400
    deliverable_text = deliverable_text.strip()
    deliverable_link = deliverable_link.strip()
    if not deliverable_text and not deliverable_link:
        return jsonify({"error": "Add deliverable details or a repository/artifact link before submitting."}), 400
    
    try:
        res = engine.submit_deliverable(
            job_id=contract_id,
            milestone_index=milestone_index,
            freelancer_id=session["user_id"],
            deliverable_text=deliverable_text,
            deliverable_link=deliverable_link or None
        )
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/approve_milestone", methods=["POST"])
def approve_milestone(contract_id):
    data = request.json or {}
    milestone_index = int(data.get("milestone_index", 0))
    contract = engine.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    
    company_id = session.get("user_id") if session.get("user_role") == "company" else contract.company_id
    
    try:
        res = engine.approve_milestone(job_id=contract_id, milestone_index=milestone_index, company_id=company_id)
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/relinquish", methods=["POST"])
def relinquish_contract(contract_id):
    if not session.get("user_id"):
        return jsonify({"error": "Sign in as the contract's company to reassign work."}), 401
    if session.get("user_role") != "company":
        return jsonify({"error": "Only the contract's company can reassign work."}), 403

    contract = engine.contracts.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found."}), 404
    if contract.company_id != session["user_id"]:
        return jsonify({"error": "Only the contract owner company can reassign work."}), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    try:
        milestone_index = int(data.get("milestone_index"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid milestone_index is required."}), 400
    reason = data.get("reason", "Company requested reassignment.")
    new_freelancer_id = data.get("new_freelancer_id")
    if not isinstance(reason, str) or not reason.strip():
        return jsonify({"error": "Provide a reason for reassignment."}), 400
    if not isinstance(new_freelancer_id, str) or not new_freelancer_id:
        return jsonify({"error": "Select a replacement freelancer."}), 400
    if new_freelancer_id == contract.current_freelancer_id:
        return jsonify({"error": "Choose a freelancer other than the currently assigned freelancer."}), 400
    if new_freelancer_id not in engine.freelancers:
        return jsonify({"error": "The selected replacement freelancer does not exist."}), 400
    
    try:
        res = engine.relinquish_and_reassign(
            job_id=contract_id,
            milestone_index=milestone_index,
            reason=reason.strip(),
            new_freelancer_id=new_freelancer_id
        )
        return jsonify({"success": True, "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/dispute", methods=["POST"])
def dispute_contract(contract_id):
    data = request.json or {}
    milestone_index = int(data.get("milestone_index", 0))
    raised_by = session.get("user_id", "Company")
    reason = data.get("reason", "Deliverable does not meet technical criteria.")
    
    try:
        dispute = engine.raise_dispute(job_id=contract_id, milestone_index=milestone_index, raised_by=raised_by, reason=reason)
        return jsonify({"success": True, "dispute": dispute})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/contracts/<contract_id>/resolve_dispute", methods=["POST"])
def resolve_dispute_contract(contract_id):
    data = request.json or {}
    milestone_index = int(data.get("milestone_index", 0))
    freelancer_split_pct = float(data.get("freelancer_split_pct", 50.0))
    notes = data.get("resolution_notes", "Arbitration consensus reached based on audit proof.")
    
    try:
        dispute = engine.resolve_dispute(job_id=contract_id, milestone_index=milestone_index, freelancer_split_pct=freelancer_split_pct, resolution_notes=notes)
        return jsonify({"success": True, "dispute": dispute})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/time/advance", methods=["POST"])
def advance_time():
    return jsonify({"success": False, "error": "Time travel is disabled; contract deadlines use the real clock."}), 410

@app.route("/api/time/reset", methods=["POST"])
def reset_time():
    return jsonify({"success": False, "error": "The real clock cannot be reset."}), 410

@app.route("/api/blockchain", methods=["GET"])
def get_blockchain():
    chain_data = [b.to_dict() for b in engine.blockchain.chain]
    pending = [tx.to_dict() for tx in engine.blockchain.pending_transactions]
    return jsonify({
        "chain": chain_data,
        "pending_transactions": pending,
        "difficulty": engine.blockchain.difficulty,
        "is_valid": engine.blockchain.is_chain_valid(),
        "wallets": engine.blockchain.wallets
    })

@app.route("/api/blockchain/mine", methods=["POST"])
def mine_block():
    new_block = engine.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")
    return jsonify({
        "success": True,
        "block": new_block.to_dict(),
        "total_blocks": len(engine.blockchain.chain)
    })

from backend.chat_store import ChatStore
chat_store = ChatStore()

# --- WhatsApp-Style Real-Time Chat API Endpoints ---

@app.route("/api/chat/rooms", methods=["GET", "POST"])
def chat_rooms():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "GET":
        users = [
            {"id": user.id, "name": user.name, "role": "company"}
            for user in engine.companies.values()
        ] + [
            {"id": user.id, "name": user.name, "role": "freelancer"}
            for user in engine.freelancers.values()
        ]
        return jsonify({
            "rooms": chat_store.get_rooms_for_user(user_id),
            "users": users,
            "current_user_id": user_id
        })

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400

    name = data.get("name")
    visibility = data.get("visibility", "public")
    member_ids = data.get("member_ids", [])
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        return jsonify({"error": "Room name must be between 1 and 80 characters"}), 400
    if visibility not in ("public", "private"):
        return jsonify({"error": "Visibility must be public or private"}), 400
    if not isinstance(member_ids, list) or any(not isinstance(member_id, str) for member_id in member_ids):
        return jsonify({"error": "member_ids must be a list of user IDs"}), 400
    if any(member_id not in engine.companies and member_id not in engine.freelancers for member_id in member_ids):
        return jsonify({"error": "One or more invited users do not exist"}), 400

    invited_members = list(dict.fromkeys(member_ids)) if visibility == "private" else []
    room = chat_store.create_room(name.strip(), visibility, user_id, invited_members)
    return jsonify({"success": True, "room": room}), 201

@app.route("/api/chat/rooms/<room_id>", methods=["GET"])
def get_room_messages(room_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    room = chat_store.get_room(room_id)
    if not room or not chat_store.can_access_room(room, user_id):
        return jsonify({"error": "Room not found"}), 404

    return jsonify({
        "room": {key: room[key] for key in ("id", "name", "visibility")},
        "messages": chat_store.get_messages_for_contract(room_id, mark_read_by=user_id),
        "current_user_id": user_id
    })

@app.route("/api/chat/rooms/<room_id>/send", methods=["POST"])
def send_room_message(room_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    room = chat_store.get_room(room_id)
    if not room or not chat_store.can_access_room(room, user_id):
        return jsonify({"error": "Room not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required"}), 400
    text = data.get("text", "")
    image_data = data.get("image_data")
    if not isinstance(text, str) or (image_data is not None and not isinstance(image_data, str)):
        return jsonify({"error": "Message text and image data must be strings"}), 400
    text = text.strip()
    if not text and not image_data:
        return jsonify({"error": "Message text or image required"}), 400

    message = chat_store.add_message(
        contract_id=room_id,
        sender_id=user_id,
        sender_name=session.get("user_name", "Anonymous"),
        sender_role=session.get("user_role", "counterpart"),
        text=text,
        image_data=image_data
    )
    return jsonify({"success": True, "message": message}), 201

@app.route("/api/chat/<contract_id>", methods=["GET"])
def get_chat_messages(contract_id):
    user_id = session.get("user_id")
    messages = chat_store.get_messages_for_contract(contract_id, mark_read_by=user_id)
    return jsonify({
        "contract_id": contract_id,
        "messages": messages,
        "current_user_id": user_id
    })

@app.route("/api/chat/<contract_id>/send", methods=["POST"])
def send_chat_message(contract_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    user_name = session.get("user_name", "Anonymous")
    user_role = session.get("user_role", "counterpart")
    
    data = request.json or {}
    text = data.get("text", "").strip()
    image_data = data.get("image_data") # base64 data URL or image link

    if not text and not image_data:
        return jsonify({"error": "Message text or image required"}), 400

    new_msg = chat_store.add_message(
        contract_id=contract_id,
        sender_id=user_id,
        sender_name=user_name,
        sender_role=user_role,
        text=text,
        image_data=image_data
    )

    return jsonify({"success": True, "message": new_msg}), 201

@app.route("/api/chat/conversations", methods=["GET"])
def get_chat_conversations():
    user_id = session.get("user_id")
    user_role = session.get("user_role")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    conversations = chat_store.get_conversations_for_user(user_id, user_role, engine.contracts)
    return jsonify({"conversations": conversations})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
