import asyncio, os, sys, logging
sys.path.insert(0, "/app/desktop/shadow_helper"); sys.path.insert(0, "/app/backend")
os.environ["HOME"] = "/tmp/helperhome"
import core
cfg = core.Config()
cfg.data.update({"folders": ["/tmp/laptop/Docs"], "downloads_folder": "/tmp/laptop/Docs", "use_chrome_logins": False, "device_name": "Test Laptop"})
cfg.save()
if len(sys.argv) > 1:
    print(core.pair(cfg, sys.argv[1]))
logging.basicConfig(level=logging.INFO)
asyncio.run(core.Helper(cfg, on_status=lambda s: print("STATUS", s, flush=True)).run())
