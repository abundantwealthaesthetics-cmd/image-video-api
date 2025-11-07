    # Download images (with browser-like headers)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    img_paths = []
    for i, url in enumerate(images):
        p = os.path.join(tmp.name, f"{i:03d}.jpg")
        try:
            r = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
        except Exception as e:
            raise HTTPException(400, f"Failed to download (network): {url} — {e}")
        if not r.ok:
            raise HTTPException(400, f"Failed to download ({r.status_code}): {url}")
        with open(p, "wb") as f:
            f.write(r.content)
        img_paths.append(p)
