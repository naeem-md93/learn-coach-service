import dotenv


ENV_PATH = dotenv.find_dotenv(".env")
ENV_LOADED = dotenv.load_dotenv(ENV_PATH)

print(f"{ENV_LOADED=} | {ENV_PATH=}")
