from __future__ import annotations

import argparse
from pathlib import Path

import requests

from camera import ensure_camera_device
from utils import guess_image_mime


class LynxAuthSDK:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def register(self, user_id: str, image_path: str | Path) -> dict:
        with open(image_path, "rb") as handle:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/register",
                data={"user_id": user_id},
                files={"image": (Path(image_path).name, handle, guess_image_mime(image_path))},
                timeout=30,
            )
        response.raise_for_status()
        return response.json()

    def verify(self, image_path: str | Path) -> dict:
        with open(image_path, "rb") as handle:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/verify",
                files={"image": (Path(image_path).name, handle, guess_image_mime(image_path))},
                timeout=30,
            )
        if response.status_code == 403:
            return response.json()
        response.raise_for_status()
        return response.json()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LynxAuth SDK scaffold CLI")
    parser.add_argument("command", choices=["register", "verify", "camera-check"])
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--user-id")
    parser.add_argument("--image")
    parser.add_argument("--device", default="/dev/video0")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sdk = LynxAuthSDK(base_url=args.base_url)

    if args.command == "camera-check":
        print(str(ensure_camera_device(args.device)))
        return

    if not args.image:
        parser.error("--image is required for register/verify")

    if args.command == "register":
        if not args.user_id:
            parser.error("--user-id is required for register")
        print(sdk.register(user_id=args.user_id, image_path=args.image))
    elif args.command == "verify":
        print(sdk.verify(image_path=args.image))


if __name__ == "__main__":
    main()
