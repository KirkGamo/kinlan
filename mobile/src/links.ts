/** Where KinLAN's pieces are downloaded or opened (README, "Install the agent" and "Get the app"). */

const RELEASES = 'https://github.com/KirkGamo/kinlan/releases';

/** The newest agent (agent-release.yml marks agent releases "latest"). */
export const AGENT_URL = `${RELEASES}/latest/download/KinLAN-Agent.exe`;
/** Short enough to type on the PC. */
export const AGENT_PAGE = 'github.com/KirkGamo/kinlan/releases';

/** The Android app, built by EAS (preview profile) and attached to the app-v release. */
export const APK_URL = `${RELEASES}/download/app-v1.0.0/KinLAN.apk`;

/** The web build, a Render static site (render.yaml, kinlan-web). */
export const WEB_URL = 'https://kinlan-web.onrender.com';

