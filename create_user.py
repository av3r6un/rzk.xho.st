import argparse
import asyncio
from getpass import getpass


async def create_user(username, password, email):
  from src.exceptions import JSRError
  from src.services import AuthService
  from src.utils.engine import dispose, session_maker

  try:
    async with session_maker.begin() as session:
      user = await AuthService.register(session, username=username, password=password, email=email)
  except JSRError as error:
    raise SystemExit(str(error)) from None
  finally:
    await dispose()

  print(f"Created user {user['username']} (uid: {user['uid']})")


def main():
  parser = argparse.ArgumentParser(description='Create a user in the configured database.')
  parser.add_argument('username')
  parser.add_argument('--email')
  args = parser.parse_args()

  username = args.username.strip()
  if not 1 <= len(username) <= 50:
    parser.error('username must be 1 to 50 characters')
  email = args.email.strip() if args.email else None
  if email is not None and not 1 <= len(email) <= 100:
    parser.error('email must be 1 to 100 characters')

  password = getpass('Password: ')
  if password != getpass('Confirm password: '):
    parser.error('passwords do not match')

  asyncio.run(create_user(username, password, email))


if __name__ == '__main__':
  main()
