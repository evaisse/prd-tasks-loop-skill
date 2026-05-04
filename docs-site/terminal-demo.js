const terminalScreen = document.getElementById("terminal-screen");

const frames = [
  {
    delay: 600,
    lines: [
      "$ python3 prd-tasks-loop/scripts/prd-tasks-loop.py --agent=codex docs/prd/2026-04-30-104512-jwt-authentication.md",
      "",
    ],
  },
  {
    delay: 850,
    lines: [
      "2026-05-04T07:38:48+00:00 Opening PRD: jwt-authentication",
      "2026-05-04T07:38:48+00:00 Active story: US-001 Reject missing tokens",
    ],
  },
  {
    delay: 900,
    lines: [
      "2026-05-04T07:38:49+00:00 Rendering a focused prompt for one story",
      "2026-05-04T07:38:50+00:00 Agent writes the change and updates the PRD",
    ],
  },
  {
    delay: 950,
    lines: [
      "2026-05-04T07:38:53+00:00 Verifying tests and quality gates",
      "2026-05-04T07:38:56+00:00 Acceptance criteria moved to done",
    ],
  },
  {
    delay: 1000,
    lines: [
      "2026-05-04T07:39:01+00:00 Story complete",
      "2026-05-04T07:39:01+00:00 Commit created with story and PRD references",
      "2026-05-04T07:39:02+00:00 Loop ready for the next user story",
      "",
      "$ _",
    ],
  },
];

const startDelay = 450;
const loopPause = 2200;

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function typeLine(text) {
  const line = document.createElement("div");
  line.className = "terminal-line";
  terminalScreen.appendChild(line);

  for (let index = 0; index < text.length; index += 1) {
    line.textContent = text.slice(0, index + 1);
    await sleep(text.startsWith("$") ? 18 : 9);
  }

  if (text === "") {
    line.innerHTML = "&nbsp;";
  }
}

async function runDemo() {
  while (true) {
    terminalScreen.textContent = "";
    await sleep(startDelay);

    for (const frame of frames) {
      for (const line of frame.lines) {
        await typeLine(line);
      }
      terminalScreen.scrollTop = terminalScreen.scrollHeight;
      await sleep(frame.delay);
    }

    await sleep(loopPause);
  }
}

runDemo();
