"""
Cortex CLI — manage vault and run plans.

Usage:
    python -m cortex vault set ANTHROPIC_API_KEY
    python -m cortex vault set OPENAI_API_KEY
    python -m cortex vault list
    python -m cortex vault delete OPENAI_API_KEY
"""

import sys
import getpass

from cortex.vault import Vault


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m cortex vault <set|list|delete> [KEY]")
        return

    if args[0] == "vault":
        vault = Vault()

        if len(args) < 2:
            print("Usage: python -m cortex vault <set|list|delete> [KEY]")
            return

        cmd = args[1]

        if cmd == "set":
            if len(args) < 3:
                print("Usage: python -m cortex vault set KEY_NAME")
                return
            key_name = args[2]
            value = getpass.getpass(f"Enter value for {key_name}: ")
            vault.set(key_name, value)
            print(f"Stored {key_name} in vault.")

        elif cmd == "list":
            keys = vault.list_keys()
            if keys:
                print("Vault keys:")
                for k in keys:
                    print(f"  {k}")
            else:
                print("Vault is empty.")

        elif cmd == "delete":
            if len(args) < 3:
                print("Usage: python -m cortex vault delete KEY_NAME")
                return
            key_name = args[2]
            vault.delete(key_name)
            print(f"Deleted {key_name} from vault.")

        else:
            print(f"Unknown vault command: {cmd}")

    elif args[0] == "start":
        from cortex.daemon import start
        start()

    elif args[0] == "stop":
        from cortex.daemon import stop
        stop()

    elif args[0] == "status":
        from cortex.daemon import status
        status()

    else:
        print(f"Unknown command: {args[0]}")
        print("Commands: vault, start, stop, status")


if __name__ == "__main__":
    main()
