// Shared by any page including partials/task_card.html
// Requires a global CSRF token variable named CSRF to be defined on the page.

function toggleSteps(subtaskId) {
    const dropdown = document.getElementById(`steps-dropdown-${subtaskId}`);
    const chevron = document.getElementById(`steps-chevron-${subtaskId}`);
    if (!dropdown) return;
    const isOpen = dropdown.style.display !== "none";
    dropdown.style.display = isOpen ? "none" : "block";
    if (chevron) chevron.textContent = isOpen ? "▾" : "▴";
}

async function toggleStep(stepId, checkbox) {
    checkbox.disabled = true;
    try {
        const res = await fetch(`/step/${stepId}/toggle/`, {
            method: "POST",
            headers: { "X-CSRFToken": CSRF },
        });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
            checkbox.checked = !checkbox.checked;
            checkbox.disabled = false;
            return;
        }
        // Reload to refresh percentage bars / status pills accurately
        // across the whole page (work rollup, dashboard tab counts, etc).
        location.reload();
    } catch {
        alert("Connection error.");
        checkbox.disabled = false;
    }
}

async function generateSteps(subtaskId) {
    try {
        const res = await fetch(`/subtask/${subtaskId}/steps/generate/`, {
            method: "POST",
            headers: { "X-CSRFToken": CSRF },
        });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        location.reload();
    } catch {
        alert("Connection error.");
    }
}

async function addStep(subtaskId) {
    const input = document.getElementById(`manual-step-${subtaskId}`);
    const title = input.value.trim();
    if (!title) return;
    const body = new URLSearchParams();
    body.append("title", title);
    try {
        await fetch(`/subtask/${subtaskId}/steps/add/`, {
            method: "POST",
            headers: { "X-CSRFToken": CSRF, "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString(),
        });
        location.reload();
    } catch {
        alert("Connection error.");
    }
}