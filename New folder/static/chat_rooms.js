(() => {
    let rooms = [];
    let currentUserId = "";
    let activeFilter = "public";
    let activeRoomId = null;
    let roomPoll = null;
    let renderedMessageCount = -1;

    const byId = (id) => document.getElementById(id);

    function notify(message) {
        if (typeof window.showToast === "function") {
            window.showToast(message, "error");
        } else {
            window.alert(message);
        }
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, options);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Chat room request failed.");
        }
        return data;
    }

    function renderRooms() {
        const list = byId("chat-room-list");
        list.replaceChildren();
        const matchingRooms = rooms.filter((room) => room.visibility === activeFilter);
        if (!matchingRooms.length) {
            const empty = document.createElement("div");
            empty.className = "p-2 text-center text-[10px] text-zinc-500";
            empty.textContent = activeFilter === "public"
                ? "No public rooms yet."
                : "No private rooms yet.";
            list.appendChild(empty);
            return;
        }

        matchingRooms.forEach((room) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "block w-full p-2 text-left hover:bg-zinc-900";
            button.addEventListener("click", () => openRoom(room));

            const title = document.createElement("span");
            title.className = "block truncate text-[11px] font-bold text-white";
            title.textContent = room.name;
            const preview = document.createElement("span");
            preview.className = "block truncate text-[10px] text-zinc-500";
            preview.textContent = room.last_message || "No messages yet";
            button.append(title, preview);
            list.appendChild(button);
        });
    }

    async function loadRooms() {
        const data = await requestJson("/api/chat/rooms");
        rooms = data.rooms;
        currentUserId = data.current_user_id;
        fillMemberPicker(data.users);
        renderRooms();
    }

    function setActiveFilter(filter) {
        activeFilter = filter;
        document.querySelectorAll("[data-room-filter]").forEach((button) => {
            const selected = button.dataset.roomFilter === activeFilter;
            button.className = selected
                ? "flex-1 rounded bg-zinc-800 px-2 py-1 text-[10px] text-white"
                : "flex-1 rounded bg-zinc-900 px-2 py-1 text-[10px] text-zinc-400";
        });
        renderRooms();
    }

    function fillMemberPicker(users) {
        const picker = byId("chat-room-members");
        picker.replaceChildren();
        users.filter((user) => user.id !== currentUserId).forEach((user) => {
            const option = document.createElement("option");
            option.value = user.id;
            option.textContent = `${user.name} (${user.role})`;
            picker.appendChild(option);
        });
    }

    function renderMessages(messages) {
        const container = byId("chat-room-messages");
        container.replaceChildren();
        messages.forEach((message) => {
            const bubble = document.createElement("div");
            bubble.className = `max-w-[80%] rounded-2xl border p-3 text-xs ${
                message.sender_id === currentUserId
                    ? "ml-auto border-white bg-white text-black"
                    : "mr-auto border-zinc-800 bg-zinc-900 text-white"
            }`;
            const sender = document.createElement("div");
            sender.className = "mb-1 text-[10px] font-bold opacity-70";
            sender.textContent = message.sender_id === currentUserId
                ? "You"
                : `${message.sender_name} · ${message.sender_role}`;
            const text = document.createElement("div");
            text.className = "whitespace-pre-wrap break-words";
            text.textContent = message.text;
            const timestamp = document.createElement("div");
            timestamp.className = "mt-1 text-right text-[9px] opacity-60";
            timestamp.textContent = new Date(message.timestamp * 1000)
                .toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
            bubble.append(sender, text, timestamp);
            container.appendChild(bubble);
        });
        if (!messages.length) {
            const empty = document.createElement("p");
            empty.className = "py-8 text-center text-xs text-zinc-500";
            empty.textContent = "Start the conversation.";
            container.appendChild(empty);
        }
        container.scrollTop = container.scrollHeight;
    }

    async function pollRoom() {
        if (!activeRoomId) return;
        try {
            const data = await requestJson(`/api/chat/rooms/${encodeURIComponent(activeRoomId)}`);
            if (data.messages.length !== renderedMessageCount) {
                renderedMessageCount = data.messages.length;
                renderMessages(data.messages);
            }
        } catch (error) {
            closeRoom();
            notify(error.message);
        }
    }

    function openRoom(room) {
        activeRoomId = room.id;
        renderedMessageCount = -1;
        byId("chat-room-modal-title").textContent = room.name;
        byId("chat-room-modal-visibility").textContent =
            room.visibility === "public"
                ? "Public · visible to all signed-in companies and freelancers"
                : "Private · invited members only";
        byId("chat-room-modal").classList.remove("hidden");
        byId("chat-room-message-input").focus();
        if (roomPoll) clearInterval(roomPoll);
        pollRoom();
        roomPoll = setInterval(pollRoom, 1500);
    }

    function closeRoom() {
        activeRoomId = null;
        if (roomPoll) clearInterval(roomPoll);
        roomPoll = null;
        byId("chat-room-modal").classList.add("hidden");
    }

    function initialize() {
        const createForm = byId("chat-room-create-form");
        const createToggle = byId("chat-room-create-toggle");
        const visibility = byId("chat-room-visibility");
        const picker = byId("chat-room-members");

        createToggle.addEventListener("click", () => {
            createForm.classList.toggle("hidden");
        });
        visibility.addEventListener("change", () => {
            picker.classList.toggle("hidden", visibility.value !== "private");
        });
        document.querySelectorAll("[data-room-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                setActiveFilter(button.dataset.roomFilter);
            });
        });
        byId("chat-room-close").addEventListener("click", closeRoom);
        byId("chat-room-modal").addEventListener("click", (event) => {
            if (event.target === byId("chat-room-modal")) closeRoom();
        });

        createForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const memberIds = visibility.value === "private"
                ? Array.from(picker.selectedOptions, (option) => option.value)
                : [];
            try {
                const data = await requestJson("/api/chat/rooms", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        name: byId("chat-room-name").value.trim(),
                        visibility: visibility.value,
                        member_ids: memberIds
                    })
                });
                createForm.reset();
                picker.classList.add("hidden");
                createForm.classList.add("hidden");
                await loadRooms();
                setActiveFilter(data.room.visibility);
                openRoom(data.room);
            } catch (error) {
                notify(error.message);
            }
        });

        byId("chat-room-message-form").addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!activeRoomId) return;
            const input = byId("chat-room-message-input");
            const text = input.value.trim();
            if (!text) return;
            try {
                await requestJson(`/api/chat/rooms/${encodeURIComponent(activeRoomId)}/send`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text })
                });
                input.value = "";
                await pollRoom();
                await loadRooms();
            } catch (error) {
                notify(error.message);
            }
        });

        loadRooms().catch((error) => notify(error.message));
    }

    document.addEventListener("DOMContentLoaded", initialize);
})();
