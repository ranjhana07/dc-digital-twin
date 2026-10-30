export function poll(task, intervalMs) {
  let stopped = false;
  let timer = null;

  async function run() {
    if (stopped) {
      return;
    }
    try {
      await task();
    } catch (error) {
      console.warn("refresh failed", error);
    }
    if (!stopped) {
      timer = setTimeout(run, intervalMs);
    }
  }

  run();
  return () => {
    stopped = true;
    clearTimeout(timer);
  };
}
