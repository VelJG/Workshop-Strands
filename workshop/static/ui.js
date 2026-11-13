const form = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const send = document.querySelector("#send");
const messages = document.querySelector("#messages");
const recentTickets = document.querySelector("#recent-tickets");
let busy = false;
const categories = { access: "Tài khoản", network: "Mạng/VPN", software: "Phần mềm", hardware: "Thiết bị", other: "Khác" };
const priorities = { low: "Thấp", normal: "Bình thường", high: "Cao" };

function ticketDetails(ticket) {
  const created = Number(ticket.created_at);
  const date = Number.isFinite(created) && created > 0
    ? `\nTạo lúc: ${new Date(created * 1000).toLocaleString("vi-VN")}` : "";
  return `Mã phiếu: ${ticket.ticket_ref}\nTiêu đề: ${ticket.title}\nLoại: ${categories[ticket.category] || categories.other}\nƯu tiên: ${priorities[ticket.priority] || priorities.normal}\nMô tả: ${ticket.content}\nTrạng thái: Chờ xử lý${date}`;
}

async function refreshTickets() {
  try {
    const response = await fetch("/tickets");
    if (!response.ok) throw new Error("Ticket list unavailable");
    const tickets = await response.json();
    if (!Array.isArray(tickets)) throw new Error("Invalid ticket list");
    recentTickets.replaceChildren();
    if (!tickets.length) {
      const empty = document.createElement("span");
      empty.className = "ticket-empty";
      empty.textContent = "Chưa có phiếu nào.";
      recentTickets.append(empty);
      return;
    }
    tickets.slice(0, 10).forEach(ticket => {
      const item = document.createElement("details");
      item.className = "ticket-item";
      const title = document.createElement("summary");
      title.textContent = `${ticket.ticket_ref} · ${ticket.title}`;
      const detail = document.createElement("span");
      detail.textContent = ticketDetails(ticket);
      item.append(title, detail);
      recentTickets.append(item);
    });
  } catch {
    recentTickets.textContent = "Chưa thể tải danh sách phiếu.";
  }
}

function bubble(role, content, source, agent, citations) {
  const item = document.createElement("div");
  item.className = `bubble ${role}`;
  const heading = document.createElement("span");
  heading.className = "meta";
  const labels = { qa: "Tra cứu chính sách", ticket: "Hỗ trợ kỹ thuật", research: "Tìm kiếm web" };
  heading.textContent = role === "user" ? "Bạn" : (labels[agent] || "Trợ lý IT");
  item.append(heading, document.createTextNode(content));
  if (source && source.length) {
    const label = document.createElement("span");
    label.className = "source";
    label.textContent = `Nguồn: ${source.join(", ")}`;
    item.append(label);
  }
  if (citations && citations.length) {
    const label = document.createElement("span");
    label.className = "source";
    label.append(document.createTextNode("Nguồn web: "));
    let linked = 0;
    citations.slice(0, 5).forEach(citation => {
      try {
        const url = new URL(citation.url);
        if (url.protocol !== "https:") return;
        if (linked++) label.append(document.createTextNode(" · "));
        const link = document.createElement("a");
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = citation.title || url.hostname;
        label.append(link);
      } catch { /* Skip malformed source URLs. */ }
    });
    item.append(label);
  }
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

function setBusy(value) {
  busy = value;
  send.disabled = value;
  input.disabled = value;
  document.querySelectorAll(".example").forEach(button => { button.disabled = value; });
}

async function post(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  let result;
  try { result = await response.json(); }
  catch { throw new Error(`Máy chủ trả về phản hồi không hợp lệ (HTTP ${response.status}).`); }
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : `Yêu cầu thất bại (HTTP ${response.status}).`);
  }
  return result;
}

async function decide(id, approve, buttons, card) {
  buttons.forEach(button => { button.disabled = true; });
  try {
    const result = await post(`/approvals/${encodeURIComponent(id)}`, { approve });
    if (result.status === "approved") {
      bubble("assistant", `Đã phê duyệt. Phiếu hỗ trợ đã được tạo.\n${ticketDetails(result)}`);
      refreshTickets();
    } else {
      bubble("assistant", "Đã từ chối. Không có phiếu nào được tạo.");
    }
    card.remove();
  } catch (error) {
    bubble("assistant", `Không thể hoàn tất quyết định: ${error.message}`);
    buttons.forEach(button => { button.disabled = false; });
  }
}

function approvalCard(result) {
  const draft = result.draft;
  const card = bubble("assistant", `Đề xuất yêu cầu hỗ trợ\nTiêu đề: ${draft.title}\nLoại: ${categories[draft.category] || categories.other}\nƯu tiên: ${priorities[draft.priority] || priorities.normal}\nMô tả: ${draft.content}\n\nChưa có phiếu nào được tạo. Bạn có phê duyệt không?`, null, "ticket");
  const actions = document.createElement("div");
  actions.className = "actions";
  const approve = document.createElement("button");
  approve.type = "button";
  approve.textContent = "Phê duyệt";
  const deny = document.createElement("button");
  deny.type = "button";
  deny.className = "secondary";
  deny.textContent = "Từ chối";
  actions.append(approve, deny);
  card.append(actions);
  const buttons = [approve, deny];
  approve.addEventListener("click", () => decide(result.approval_id, true, buttons, card));
  deny.addEventListener("click", () => decide(result.approval_id, false, buttons, card));
}

async function sendMessage(message) {
  if (busy || !message.trim()) return;
  const trimmed = message.trim();
  bubble("user", trimmed);
  input.value = "";
  setBusy(true);
  try {
    const result = await post("/chat", { message: trimmed });
    if (result.kind === "approval_required") approvalCard(result);
    else if (result.kind === "answer") bubble("assistant", result.answer, result.sources, result.agent, result.citations);
    else throw new Error("Máy chủ trả về loại phản hồi không hợp lệ.");
  } catch (error) {
    bubble("assistant", `Không thể gửi tin nhắn: ${error.message}`);
  } finally {
    setBusy(false);
    input.focus();
  }
}

form.addEventListener("submit", event => {
  event.preventDefault();
  sendMessage(input.value);
});
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll(".example").forEach(button => {
  button.addEventListener("click", () => sendMessage(button.dataset.message));
});
refreshTickets();
