const terminalScreen = document.getElementById("terminal-screen");

const frames = [
  {
    delay: 600,
    lines: [
      "$ python3 prd-tasks-loop/scripts/prd-tasks-loop.py --agent=codex docs/prd/2026-04-30-104512-happy-path.md",
      "",
    ],
  },
  {
    delay: 850,
    lines: [
      "2026-05-04T07:38:48+00:00 1/1 2026-04-30-104512-happy-path.md",
      "2026-05-04T07:38:48+00:00 US-001 running",
    ],
  },
  {
    delay: 900,
    lines: [
      "2026-05-04T07:38:56+00:00 US-001 passed",
      "2026-05-04T07:38:56+00:00 US-002 running",
    ],
  },
  {
    delay: 950,
    lines: [
      "2026-05-04T07:39:03+00:00 US-002 passed",
      "2026-05-04T07:39:03+00:00 Completed: /workspace/docs/prd/2026-04-30-104512-happy-path.md",
      "# success removes .json.log and .progress.log",
      "",
    ],
  },
  {
    delay: 900,
    lines: [
      "$ python3 prd-tasks-loop/scripts/prd-tasks-loop.py --agent=sleep-agent --timeout 1s --retries 2 docs/prd/2026-04-30-104512-timeout-case.md",
      "",
      "2026-05-04T07:40:00+00:00 US-001 running",
      "2026-05-04T07:40:00+00:00 US-001 failed (exit 124)",
    ],
  },
  {
    delay: 900,
    lines: [
      "2026-05-04T07:40:00+00:00 US-001 backing off 0s before retry",
      "2026-05-04T07:40:00+00:00 US-001 retrying",
      "2026-05-04T07:40:01+00:00 US-001 retry 2/2",
      "2026-05-04T07:40:02+00:00 US-001 failed (2/2, exit 124)",
      "2026-05-04T07:40:02+00:00 US-001 failed permanently",
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
