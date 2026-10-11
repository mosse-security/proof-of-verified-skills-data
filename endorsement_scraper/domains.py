from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


CYBER_DOMAINS = (
    "cloud-security",
    "cyber-defense",
    "devsecops",
    "digital-forensics",
    "grc",
    "incident-response",
    "open-source-intelligence",
    "penetration-testing",
    "red-teaming",
    "reverse-engineering",
    "vulnerability-research",
)
UNKNOWN_DOMAIN = "unknown"
ALLOWED_DOMAINS = (*CYBER_DOMAINS, UNKNOWN_DOMAIN)


class DomainMappingError(ValueError):
    pass


_RULES: dict[str, tuple[str, ...]] = {
    "cloud-security": (
        r"\bcloud security\b",
        r"\b(?:AWS|Amazon Web Services|Azure|GCP|Google Cloud)\b",
        r"\b(?:Kubernetes|K8s|container security|cloud native|serverless|IAM)\b",
        r"\b(?:S3 bucket|EC2|EKS|AKS|Lambda function|cloud metadata service)\b",
        r"\b(?:Entra ID|Azure AD|cloud identity|multi[ -]tenant|SaaS security)\b",
    ),
    "cyber-defense": (
        r"\bcyber defen[cs]e\b",
        r"\bblue team(?:ing)?\b",
        r"\bdefen[cs]ive security\b",
        r"\b(?:SOC|security operations|detection engineering)\b",
        r"\b(?:IDS|IPS|intrusion detection|firewall|network defense|hardening)\b",
        r"\b(?:SIEM|EDR|XDR|endpoint detection|threat detection)\b",
        r"\b(?:security telemetry|security monitoring|honeypot|honeynet)\b",
        r"\b(?:YARA|Sigma rule|detection rule|threat intelligence)\b",
        r"\b(?:defending|protecting|mitigating) (?:against|systems?|networks?|endpoints?)\b",
        r"\b(?:DDoS protection|anti[ -]malware|security program|secure configuration)\b",
        r"\b(?:attack detection|attack prevention|intrusion prevention)\b",
        r"\b(?:cyber|network|endpoint|host|system) defen[cs]e\b",
        r"\b(?:malware|threat|intrusion|anomaly) detect(?:ion|ing)\b",
        r"\b(?:intrusion management|intrusion system|network monitoring)\b",
    ),
    "devsecops": (
        r"\bDevSecOps\b",
        r"\b(?:CI/CD|secure SDLC|software supply chain)\b",
        r"\b(?:SAST|DAST|code scanning|dependency scanning)\b",
        r"\b(?:container security|infrastructure as code|IaC security)\b",
        r"\b(?:GitHub Actions|GitLab CI|build pipeline|deployment pipeline)\b",
        r"\b(?:SBOM|software bill of materials|artifact signing|code signing)\b",
        r"\b(?:secrets scanning|software composition analysis|SCA)\b",
        r"\b(?:software |dependency |package )?supply[ -]chain (?:attack|compromise|security)\b",
        r"\b(?:dependency confusion|malicious package|package registry attack)\b",
        r"\b(?:build system security|secure build|pipeline security)\b",
        r"\b(?:upstream|open[ -]source) (?:project|package|library).{0,80}\b(?:backdoor|compromis)(?:e|ed|es|ing)?\b",
    ),
    "digital-forensics": (
        r"\bdigital forensics?\b",
        r"\bcomputer forensics?\b",
        r"\b(?:memory|disk|mobile|network) forensics?\b",
        r"\bforensic (?:analysis|artifact|investigation|image)\b",
        r"\bmalware forensics?\b",
        r"\b(?:evidence acquisition|forensic timeline|timeline analysis)\b",
        r"\b(?:memory dump|disk image|filesystem artifact|log forensics)\b",
        r"\banti[ -]?forensics?\b",
        r"\bforensic(?:s|ally)?\b",
    ),
    "grc": (
        r"\bGRC\b",
        r"\bgovernance,? risk,? and compliance\b",
        r"\b(?:risk management|security compliance|security governance)\b",
        r"\b(?:ISO ?27001|SOC 2|PCI DSS|NIST CSF)\b",
        r"\bsecurity (?:audit|policy|policies|control framework)\b",
        r"\b(?:regulatory compliance|security regulation|data protection law)\b",
        r"\b(?:GDPR|HIPAA|FedRAMP|CIS Controls)\b",
        r"\b(?:cybersecurity|cyber security|privacy) polic(?:y|ies)\b",
        r"\b(?:cyber law|computer crime law|security regulation)\b",
    ),
    "incident-response": (
        r"\bincident response\b",
        r"\bDFIR\b",
        r"\b(?:breach|ransomware) response\b",
        r"\b(?:incident handling|incident investigation|threat hunting)\b",
        r"\b(?:incident triage|breach containment|containment and eradication)\b",
        r"\b(?:post[ -]incident|incident responder|compromise assessment)\b",
    ),
    "open-source-intelligence": (
        r"\bOSINT\b",
        r"\bopen[ -]source intelligence\b",
        r"\b(?:social media intelligence|SOCMINT)\b",
        r"\b(?:internet reconnaissance|online reconnaissance|geolocation)\b",
        r"\b(?:passive reconnaissance|public records research)\b",
        r"\b(?:Shodan|Maltego|Google dork(?:ing|s)?)\b",
        r"\b(?:OSINT|recon|reconnaissance) (?:tool|technique|workflow|on|of|for)\b",
        r"\b(?:public|open) data (?:collection|research|investigation)\b",
    ),
    "penetration-testing": (
        r"\bpenetration test(?:ing|er|ers)?\b",
        r"\bpen[ -]?test(?:ing|er|ers)?\b",
        r"\bsecurity assessment\b",
        r"\b(?:web|mobile|network|application) security testing\b",
        r"\b(?:offensive security assessment|attack surface assessment)\b",
        r"\b(?:Burp Suite|Metasploit|Nmap)\b",
        r"\b(?:ethical hacking|offensive security testing|attack surface testing)\b",
        r"\b(?:web|network|mobile|wireless|application) hacking\b",
        r"\b(?:network|service|host|wireless) (?:recon|reconnaissance|scanning|sniffing)\b",
        r"\b(?:fingerprinting|enumeration) (?:a |the )?(?:network|host|service|target|system)\b",
        r"\b(?:attack|security) surface mapping\b",
    ),
    "red-teaming": (
        r"\bred team(?:ing|er|ers)?\b",
        r"\badversary emulation\b",
        r"\battack simulation\b",
        r"\bcommand and control\b",
        r"\bC2 infrastructure\b",
        r"\blateral movement\b",
        r"\b(?:MITRE ATT&CK|adversary simulation|purple team(?:ing)?)\b",
        r"\b(?:initial access|defen[cs]e evasion|credential access|persistence)\b",
        r"\b(?:phishing campaign|payload delivery|operator tradecraft|red team OPSEC)\b",
        r"\b(?:post[ -]exploitation|offensive tradecraft|implant development)\b",
        r"\b(?:shellcode|rootkit|command-and-control|malware evasion)\b",
        r"\b(?:social engineering|spear[ -]?phishing|vishing|pretexting)\b",
        r"\b(?:physical intrusion|physical red team|badge cloning)\b",
    ),
    "reverse-engineering": (
        r"\breverse engineer(?:ing|ed)?\b",
        r"\bbinary analysis\b",
        r"\b(?:disassembl|decompil)(?:e|er|ing|ation)\w*\b",
        r"\bmalware analysis\b",
        r"\bfirmware analysis\b",
        r"\b(?:assembly language|machine code|bytecode|debugger)\b",
        r"\b(?:deobfuscat|unpack)(?:e|ion|ing)\w*\b",
        r"\b(?:protocol reversing|firmware reversing|BootROM)\b",
        r"\b(?:reverse|reversing) (?:a |the )?(?:protocol|firmware|binary|driver|malware|app)\b",
        r"\b(?:program analysis|code recovery|binary instrumentation)\b",
        r"\b(?:Ghidra|IDA Pro|Binary Ninja|radare2|Rizin)\b",
        r"\b(?:de[ -]?obfuscat|unpack)(?:e|ion|ing)\w*\b",
        r"\b(?:packer|packed binary|executable image|bootloader internals)\b",
    ),
    "vulnerability-research": (
        r"\bvulnerabilit(?:y|ies)\b",
        r"\bCVE-\d{4}-\d+\b",
        r"\b(?:zero[ -]?day|0day|0-day)\b",
        r"\bexploit (?:development|research|technique|chain)\b",
        r"\b(?:fuzzing|fuzzer|bug bounty|memory corruption)\b",
        r"\b(?:remote code execution|RCE)\b",
        r"\b(?:CVE|CWE)(?:s|'s)?\b",
        r"\b(?:exploit chain|exploitation|proof[ -]of[ -]concept|PoC)\b",
        r"\b(?:arbitrary code execution|privilege escalation|auth(?:entication)? bypass)\b",
        r"\b(?:sandbox escape|use[ -]after[ -]free|buffer overflow|heap overflow)\b",
        r"\b(?:SQL injection|XSS|cross[ -]site scripting|SSRF|deserialization)\b",
        r"\b(?:race condition|side[ -]channel|fault injection|logic flaw)\b",
        r"\b(?:responsible disclosure|coordinated disclosure|security advisory)\b",
        r"\b(?:security bug|security flaw|security weakness)s?\b",
        r"\b(?:bug hunting|vulnerability hunting|hunting bugs)\b",
        r"\b(?:bypass|bypassing|bypassed|takeover|hijack|hijacking|jailbreak)\w*\b",
        r"\b(?:sandbox|container|virtual machine|VM).{0,30}\bescape(?:d|s|ing)?\b",
        r"\b(?:pwn|pwned|pwnage|owned|shellcode|rootkit|backdoor)\b",
        r"\b(?:credential|password|PIN|hash) crack(?:ing|ed)?\b",
        r"\b(?:code|command|keystroke|prompt|DLL|process) injection\b",
        r"\b(?:weaponiz|compromis)(?:e|ed|es|ing|ation)\w*\b",
        r"\b(?:attack|attacks) against\b",
        r"\bsecurity (?:evaluation|assessment) of\b",
        r"\bassess(?:ing|ment of) (?:the )?security\b",
        r"\b(?:breaking|defeating) (?:the )?(?:security|authentication|authorization|encryption|sandbox|isolation)\b",
        r"\bexploits?\b",
        r"\b(?:pwn|own)(?:ed|ing|age|s)?\b",
        r"\bbackdoor(?:ed|ing|s)?\b",
        r"\b(?:attack|attacking|abuse|abusing) (?:a |an |the )?(?:protocol|system|device|service|application|app|kernel|driver|TPM|DNS|RFID|lock)\b",
        r"\b(?:spoofing|tampering|forgery) (?:attack|technique|a |an |the )?\w*\b",
        r"\b(?:security|privacy) (?:risk|issue|problem)s? (?:in|of|with)\b",
        r"\b(?:hacking|breaking) (?:a |an |the |your )?(?:system|device|application|app|protocol|kernel|driver|firmware|bootloader|access control|authentication|TEE)\b",
        r"\b(?:fool|evade|defeat)(?:ing|ed|s)? (?:a |an |the )?(?:detector|classifier|recognition|security control)\b",
        r"\bhacking .{0,40}\b(?:authentication|authorization|access control|secure enclave)\b",
        r"\bsecurity of (?:a |an |the )?\w+\b",
        r"\b(?:hardware|embedded|device|firmware) hacking\b",
    ),
}

_COMPILED_RULES = {
    domain: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for domain, patterns in _RULES.items()
}
_CANONICAL = {domain.casefold(): domain for domain in ALLOWED_DOMAINS}


def detect_domains(*values: Any) -> tuple[str, ...]:
    """Detect all matching cyber domains in deterministic taxonomy order."""

    text = " ".join(_flatten_text(value) for value in values if value is not None)
    detected = tuple(
        domain
        for domain in CYBER_DOMAINS
        if any(pattern.search(text) for pattern in _COMPILED_RULES[domain])
    )
    return detected or (UNKNOWN_DOMAIN,)


def normalize_domains(values: Iterable[str] | str | None) -> tuple[str, ...]:
    """Validate, canonicalize, deduplicate, and order explicit domains."""

    if values is None:
        return (UNKNOWN_DOMAIN,)
    if isinstance(values, str):
        values = (values,)
    canonical: set[str] = set()
    invalid: list[str] = []
    for value in values:
        if not isinstance(value, str):
            invalid.append(repr(value))
            continue
        matched = _CANONICAL.get(value.strip().casefold())
        if matched is None:
            invalid.append(value)
        else:
            canonical.add(matched)
    if invalid:
        raise DomainMappingError(
            "Unsupported cyber domain(s): "
            + ", ".join(invalid)
            + ". Allowed values: "
            + ", ".join(ALLOWED_DOMAINS)
        )
    known = tuple(domain for domain in CYBER_DOMAINS if domain in canonical)
    return known or (UNKNOWN_DOMAIN,)


def validate_record_domains(record: Mapping[str, Any], *, source: str = "record") -> None:
    """Require a canonical, non-empty domains array on an output record."""

    if "domains" not in record:
        raise DomainMappingError(f"{source} is missing required 'domains'")
    values = record["domains"]
    if not isinstance(values, list) or not values:
        raise DomainMappingError(f"{source}.domains must be a non-empty JSON array")
    normalized = normalize_domains(values)
    if values != list(normalized):
        raise DomainMappingError(
            f"{source}.domains must be canonical and ordered; expected {list(normalized)!r}"
        )


def validate_domain_output_files(
    paths: Iterable[Path], *, expected_records: int | None = None
) -> int:
    """Validate every endorsement record in collection-scraper JSON outputs."""

    unique_paths = tuple(dict.fromkeys(Path(path) for path in paths))
    if expected_records and not unique_paths:
        raise DomainMappingError(
            "A collection scraper emitted endorsements without reporting output files"
        )
    count = 0
    for path in unique_paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DomainMappingError(f"Cannot validate domain output {path}: {exc}") from exc
        records = document if isinstance(document, list) else [document]
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise DomainMappingError(f"{path}[{index}] must be a JSON object")
            validate_record_domains(record, source=f"{path}[{index}]")
            count += 1
    if expected_records is not None and count != expected_records:
        raise DomainMappingError(
            f"Collection scraper reported {expected_records} endorsements but its "
            f"output files contain {count} records"
        )
    return count


def _flatten_text(value: Any) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_flatten_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


