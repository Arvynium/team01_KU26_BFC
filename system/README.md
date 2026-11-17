## 1. Analysis — System

### A. In-House Code Vulnerabilities

The in-house source code in `/src` contains intentionally introduced vulnerabilities.
You must exploit these vulnerabilities and submit a vulnerability report that includes a screenshot showing the FLAG output.

### B. Open-Source Software Vulnerabilities

The `/third_party` directory contains external OSS used by the project. Outdated versions with known vulnerabilities have been intentionally included. You may use any approach to discover and analyze vulnerabilities in these components.

For OSS vulnerabilities, you must explain the root cause, impact, and attack path in detail, and clearly state whether the vulnerability can be reproduced in the provided environment and the evidence supporting your conclusion. The existence of a known CVE alone does not establish that the vulnerability can occur in this project.

- If reproduced: Provide the required input, execution steps, and observed results.
- If reproduction is incomplete: Describe the steps attempted, the results, why reproduction was not completed, and what requires further investigation.
- If determined not to be reproducible: Provide concrete evidence from the relevant code and configuration showing that no call path reaches the vulnerable code, or that the required configuration or input conditions cannot be satisfied in the provided environment.

## 2. Recommended Workflow

### Step 1. Understand the Project Structure and Environment

Run the project and identify its main features, user input points, and locations where external libraries are used.

### Step 2. Discover Vulnerability Candidates — Detect

Collect potential vulnerabilities through source code review and analysis tools.

- Static analysis: Identify unsafe operations and vulnerability patterns in the source code.
- Dependency analysis: Identify external libraries and their versions, and check for known vulnerabilities.
-  Dynamic analysis: Run the program and observe its behavior with different inputs.

You may freely choose analysis tools appropriate for the project’s language and structure. In your report, explain which tools you used and why you selected them.

### Step 3. Analyze Root Causes and Attack Paths — Analyze

Use AI to review the analysis results and relevant code, and consider the following questions:

- What operation or implementation detail causes the vulnerability?
- Through which functions and processing steps does the input reach the vulnerable code?
- What input conditions are required to trigger the vulnerability?
- Can the vulnerability actually be triggered? Do input validation or execution conditions prevent the attack?

### Step 4. Validate the Findings — Validate

Validate findings from manual code review, AI, or analysis tools by running the program yourself.

Classify and document the validation result using one of the following categories:

- Reproduced: Vulnerable behavior was directly observed using an input in the provided environment.
- Potentially reproducible, but reproduction incomplete: Code analysis confirmed the attack path and required conditions, but execution-based reproduction has not been completed.
- Not reproducible in the provided environment: The required configuration or call path is absent, and evidence confirms that the vulnerability cannot occur in the provided environment.
- Undetermined: Available evidence is insufficient, or environmental constraints prevent a conclusion about whether the vulnerability can occur.

### Step 5. Develop and Run a PoC / Exploit — Exploit

Create and execute inputs or code that trigger the vulnerability in the provided Docker environment.

Record the exploit code or payload, commands, and output so that another person can reproduce the same result.

For in-house code vulnerabilities where a FLAG is provided, include evidence of successful **FLAG retrieval**.

### Step 6. Submit a Private Vulnerability Report — Report

Submit your findings privately through **Security and quality → Report a vulnerability** in the course GitHub repository.


## Build and Run

The project requires a Linux environment with GCC or Clang, CMake 3.16 or later, Make, and pthread. Python and CTest are not required for the build.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j2
./build/bfc
```

## Run the Docker Server and Connect Using nc

```bash
docker build -t bfc-proj .
docker run --rm -d --name bfc-proj -p 1337:1337 bfc-proj
nc 127.0.0.1 1337
```

### Running on macOS

This project targets Linux and should not be built directly on macOS.

Install and start Docker Desktop, then run the following commands from the project root:

```bash
docker build --platform linux/amd64 -t bfc .
docker run --rm --platform linux/amd64 \
  -p 127.0.0.1:1337:1337 bfc
```

While the server is running, open another terminal and connect:

```bash
nc 127.0.0.1 1337
```

