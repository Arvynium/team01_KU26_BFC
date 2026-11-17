# CCS-KU BFC: Relay

[한국어](README.ko.md)

Relay is a shared gear library used for the CCS-KU Bug Finding Challenge, a Korea University course security practice. Browse available kits, open loan documents, record return conditions, and prepare item photos and manuals. Investigate these workflows using the running application and its source code.

## Run Locally

Install Docker Desktop on macOS or Windows. On Ubuntu 22.04 or 26.04, install Docker Engine and the Compose plugin. Start Docker. Generate private values for this local practice instance, then start the stack from the repository root:

```bash
python3 scripts/init_practice.py
docker compose up --build
```

On Windows, use `py -3 scripts/init_practice.py` if `python3` is unavailable. The script creates `.env` once and never overwrites it. The sample `.env.example` has no usable secrets. The course team server uses separate team-specific environment files; do not use a practice `.env` for grading.

Open [http://localhost:3000](http://localhost:3000). The local practice environment has no login. The first build of the image and document workers can take several minutes. Stop the stack with `docker compose down`.

The **Reset practice environment** control clears saved views, pickup bundles, condition reports, approvals, and preview jobs. It does not replace a full Docker rebuild.

## Workspace

- **Gear inventory:** search available kits, save a filtered view, export a pickup sheet, and prepare a pickup bundle.
- **Loan documents:** open pickup and care information by document reference.
- **Condition reports:** write return notes and request a staff review.
- **Item photos:** create image previews for listings.
- **Manual viewer:** render equipment and loan documents.

## Software Inventory

Download the source ZIP provided by the course and submit it to IoTcube to generate a software bill of materials. Compare the result with the source and Docker build files. Do not treat a component/version match alone as proof that a vulnerability is reachable.

Reporting instructions will be announced separately by the course staff. Test only your assigned practice environment.
