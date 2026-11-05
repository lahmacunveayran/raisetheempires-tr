import logging, sys
sys.argv = ["probe5_kayit"]
import save_engine
print([(type(h), getattr(h, "baseFilename", None)) for h in logging.getLogger().handlers])
print(save_engine.log_path(), save_engine.my_games_path())
