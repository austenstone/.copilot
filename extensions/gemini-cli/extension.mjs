import { joinSession } from "@github/copilot-sdk/extension";
import { execFile } from "node:child_process";
import { tmpdir } from "node:os";

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_MODEL = "gemini-flash-latest";
const MAX_TIMEOUT_MS = 600_000;

function clean(text) {
    return (text || "")
        .split("\n")
        .filter((line) => !/True color \(24-bit\) support/.test(line))
        .join("\n")
        .trim();
}

function timeoutFromSeconds(timeoutSeconds) {
    if (typeof timeoutSeconds !== "number" || !Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
        return DEFAULT_TIMEOUT_MS;
    }

    return Math.min(Math.round(timeoutSeconds * 1000), MAX_TIMEOUT_MS);
}

function runGemini(prompt, { model, cwd, timeoutSeconds } = {}) {
    const args = ["--skip-trust", "-p", prompt, "-m", model || DEFAULT_MODEL];
    const timeout = timeoutFromSeconds(timeoutSeconds);

    return new Promise((resolve, reject) => {
        execFile(
            "gemini",
            args,
            {
                cwd: cwd || tmpdir(),
                timeout,
                maxBuffer: 10 * 1024 * 1024,
                env: process.env,
            },
            (err, stdout, stderr) => {
                const out = clean(stdout);
                if (err) {
                    if (err.killed) {
                        return reject(new Error(`Gemini CLI timed out after ${timeout / 1000}s`));
                    }

                    return reject(new Error(clean(stderr) || err.message));
                }

                resolve(out || clean(stderr) || "(no output)");
            },
        );
    });
}

const session = await joinSession({
    tools: [
        {
            name: "gemini_cli",
            description:
                "Run Google's Gemini CLI as a general-purpose peer model. " +
                "Use for web-grounded research, second opinions, docs lookup, summarization, code review, and long synthesis. " +
                "For current facts, tell Gemini to use web search in the prompt. Prefer parallel/background use for independent work.",
            parameters: {
                type: "object",
                properties: {
                    prompt: {
                        type: "string",
                        description: "The full task or question for Gemini CLI. Include whether it should use web search.",
                    },
                    model: {
                        type: "string",
                        description:
                            "Optional Gemini model override. Defaults to gemini-flash-latest. Examples: gemini-pro-latest, gemini-2.5-flash, gemini-2.5-pro.",
                    },
                    cwd: {
                        type: "string",
                        description:
                            "Optional working directory. Omit unless Gemini should read local files or repo context.",
                    },
                    timeoutSeconds: {
                        type: "number",
                        description: "Optional timeout in seconds. Defaults to 120. Maximum is 600.",
                    },
                },
                required: ["prompt"],
            },
            skipPermission: true,
            handler: async (args) => {
                if (!args?.prompt || typeof args.prompt !== "string") {
                    return { textResultForLlm: "Error: 'prompt' is required.", resultType: "failure" };
                }

                try {
                    return await runGemini(args.prompt, {
                        model: args.model,
                        cwd: args.cwd,
                        timeoutSeconds: args.timeoutSeconds,
                    });
                } catch (e) {
                    return {
                        textResultForLlm: `gemini_cli failed: ${e.message}`,
                        resultType: "failure",
                    };
                }
            },
        },
    ],
});

await session.log("gemini-cli extension ready");