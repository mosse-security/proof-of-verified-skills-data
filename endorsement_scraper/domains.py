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
    "identity-and-access-management",
    "iot-security",
    "operational-technology-security",
    "threat-hunting",
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

_RULES.update({
    "identity-and-access-management": (
        r"\b(?:identity and access management|IAM|IdAM)\b",
        r"\b(?:identity|authorization|access control|privileged access|PAM) (?:management|security|governance)\b",
        r"\b(?:single sign-on|SSO|OAuth|OpenID|OIDC|SAML|Active Directory|LDAP|Kerberos)\b",
        r"\b(?:credential|password|identity|directory) (?:security|management|governance)\b",
    ),
    "iot-security": (
        r"\b(?:IoT|Internet of Things|smart home|connected device|embedded device)\b",
        r"\b(?:device security|IoT security|MQTT|Zigbee|Z-Wave)\b",
    ),
    "operational-technology-security": (
        r"\b(?:OT security|operational technology|ICS|SCADA|PLC|industrial control)\b",
        r"\b(?:industrial protocol|Modbus|DNP3|safety system|critical infrastructure)\b",
    ),
    "threat-hunting": (
        r"\b(?:threat hunting|proactive hunting|hypothesis-driven hunting)\b",
        r"\b(?:hunt(?:ing)? for adversar(?:y|ies)|hunt(?:ing)? malicious activity)\b",
    ),
})

_SUBSPECIALTY_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "cloud-security": {
        "cloud-architecture-and-security-design": (r"cloud architecture", r"cloud security design"),
        "cloud-identity-and-access": (r"cloud IAM", r"cloud identity", r"Azure AD", r"Entra ID"),
        "cloud-configuration-and-posture-management": (r"cloud misconfiguration", r"cloud posture", r"CSPM"),
        "cloud-workload-and-virtual-machine-security": (r"cloud workload", r"virtual machine security", r"EC2", r"EKS", r"AKS"),
        "container-and-kubernetes-security": (r"container security", r"Kubernetes", r"\bK8s\b"),
        "cloud-network-security": (r"cloud network", r"VPC security", r"virtual network"),
        "cloud-secrets-and-key-management": (r"cloud secrets", r"cloud key management", r"KMS", r"metadata service"),
        "cloud-attack-paths-and-lateral-movement": (r"cloud attack path", r"cloud lateral movement"),
        "cloud-detection-and-incident-response": (r"cloud detection", r"cloud incident response"),
        "serverless-security": (r"serverless", r"Lambda function"),
    },
    "cyber-defense": {
        "security-operations-and-soc-practice": (r"\bSOC\b", r"security operations"),
        "network-defense-and-monitoring": (r"network defense", r"network monitoring"),
        "endpoint-and-host-defense": (r"endpoint defense", r"host defense", r"EDR", r"XDR"),
        "detection-engineering": (r"detection engineering", r"detection rule", r"Sigma rule", r"YARA"),
        "threat-intelligence-operations": (r"threat intelligence", r"cyber threat intelligence"),
        "cyber-resilience-and-critical-infrastructure-defense": (r"cyber resilience", r"critical infrastructure defense"),
        "ddos-defense-and-availability-protection": (r"DDoS", r"availability protection"),
        "deception-and-honeypots": (r"honeypot", r"honeynet", r"deception"),
        "security-monitoring-and-alert-triage": (r"security monitoring", r"alert triage", r"SIEM"),
        "defensive-architecture": (r"defensive architecture", r"defense architecture"),
    },
    "devsecops": {
        "secure-software-development-lifecycle": (r"secure SDLC", r"secure software development"),
        "ci-cd-and-pipeline-security": (r"CI/CD", r"build pipeline", r"deployment pipeline"),
        "application-security-automation": (r"application security automation", r"code scanning"),
        "infrastructure-as-code-security": (r"infrastructure as code", r"IaC security"),
        "software-supply-chain-security": (r"software supply chain", r"supply-chain security"),
        "dependency-and-package-security": (r"dependency security", r"dependency confusion", r"package security"),
        "open-source-software-security": (r"open-source software", r"open source package"),
        "secrets-management-in-development": (r"secrets scanning", r"development secrets"),
        "secure-containers-and-build-systems": (r"secure build", r"build system security", r"container security"),
        "security-testing-integration": (r"SAST", r"DAST", r"security testing integration"),
    },
    "digital-forensics": {
        "disk-and-filesystem-forensics": (r"disk forensics", r"filesystem forensics", r"disk image"),
        "memory-forensics": (r"memory forensics", r"memory dump"),
        "network-forensics": (r"network forensics", r"network evidence"),
        "endpoint-and-host-forensics": (r"endpoint forensics", r"host forensics"),
        "mobile-device-forensics": (r"mobile forensics", r"mobile-device forensics"),
        "cloud-forensics": (r"cloud forensics", r"cloud evidence"),
        "malware-forensics": (r"malware forensics", r"forensic malware"),
        "timeline-and-artifact-analysis": (r"timeline analysis", r"artifact analysis", r"forensic artifact"),
        "evidence-acquisition-and-preservation": (r"evidence acquisition", r"evidence preservation"),
        "forensic-tooling-and-laboratory-practice": (r"forensic tool", r"forensic laboratory"),
    },
    "grc": {
        "security-governance": (r"security governance", r"governance"),
        "risk-management": (r"risk management", r"risk assessment"),
        "risk-quantification": (r"risk quantification", r"quantifying risk"),
        "compliance-and-audit": (r"compliance", r"security audit", r"ISO ?27001", r"PCI DSS"),
        "security-policy-and-standards": (r"security policy", r"security standard", r"NIST CSF"),
        "privacy-and-data-protection": (r"privacy", r"data protection", r"GDPR", r"HIPAA"),
        "cyber-law-and-regulation": (r"cyber law", r"computer crime law", r"regulation"),
        "third-party-and-supplier-risk": (r"third-party risk", r"supplier risk"),
        "business-continuity-and-resilience-planning": (r"business continuity", r"resilience planning"),
        "security-awareness-and-human-risk": (r"security awareness", r"human risk"),
    },
    "incident-response": {
        "incident-handling-and-triage": (r"incident handling", r"incident triage"),
        "breach-response": (r"breach response", r"breach investigation"),
        "ransomware-response": (r"ransomware response", r"ransomware recovery"),
        "containment-eradication-and-recovery": (r"containment and eradication", r"eradication and recovery"),
        "crisis-management-and-communications": (r"crisis management", r"incident communications"),
        "incident-coordination-and-case-management": (r"incident coordination", r"case management"),
        "response-playbooks-and-tabletop-exercises": (r"response playbook", r"tabletop exercise"),
        "dfir-operations": (r"\bDFIR\b", r"DFIR operations"),
    },
    "open-source-intelligence": {
        "open-web-investigations": (r"open-web investigation", r"online investigation"),
        "social-media-intelligence": (r"social media intelligence", r"SOCMINT"),
        "dark-web-intelligence": (r"dark web", r"dark-web intelligence"),
        "source-verification-and-validation": (r"source verification", r"source validation"),
        "geospatial-and-imagery-intelligence": (r"geospatial", r"geolocation", r"imagery intelligence"),
        "cyber-threat-intelligence-collection": (r"OSINT collection", r"intelligence collection"),
        "attribution-and-identity-research": (r"attribution", r"identity research"),
    },
    "penetration-testing": {
        "web-application-penetration-testing": (r"web application", r"web security testing", r"web hacking"),
        "api-penetration-testing": (r"API security", r"API testing", r"API hacking"),
        "network-penetration-testing": (r"network penetration", r"network testing", r"network scanning"),
        "cloud-penetration-testing": (r"cloud penetration", r"cloud security assessment"),
        "mobile-application-penetration-testing": (r"mobile application testing", r"mobile security testing"),
        "thick-client-application-testing": (r"thick-client", r"thick client"),
        "wireless-and-radio-testing": (r"wireless testing", r"radio testing", r"RFID"),
        "database-testing": (r"database penetration", r"database testing"),
        "infrastructure-and-internal-network-testing": (r"internal network testing", r"infrastructure testing"),
        "physical-and-facilities-testing": (r"physical penetration", r"facilities testing"),
        "iot-and-device-penetration-testing": (r"IoT penetration", r"device penetration"),
        "ot-and-ics-penetration-testing": (r"OT penetration", r"ICS penetration"),
    },
    "red-teaming": {
        "adversary-simulation": (r"adversary simulation", r"adversary emulation"),
        "assumed-breach-exercises": (r"assumed breach", r"assumed-breach"),
        "purple-teaming": (r"purple team", r"purple teaming"),
        "phishing-and-spear-phishing": (r"phishing", r"spear[ -]?phishing"),
        "social-engineering": (r"social engineering", r"vishing", r"pretexting"),
        "command-and-control-operations": (r"command and control", r"C2 infrastructure"),
        "offensive-tooling": (r"offensive tooling", r"offensive tool"),
        "operational-security-and-tradecraft": (r"OPSEC", r"operator tradecraft"),
        "physical-red-teaming": (r"physical red team", r"physical intrusion"),
        "breach-and-attack-simulation": (r"breach and attack simulation", r"attack simulation"),
    },
    "reverse-engineering": {
        "malware-analysis": (r"malware analysis", r"malware reversing"),
        "binary-and-application-reverse-engineering": (r"binary analysis", r"application reverse"),
        "firmware-reverse-engineering": (r"firmware analysis", r"firmware reversing"),
        "hardware-reverse-engineering": (r"hardware reverse", r"hardware analysis"),
        "operating-system-internals": (r"operating-system internals", r"OS internals", r"kernel internals"),
        "protocol-reverse-engineering": (r"protocol reverse", r"protocol reversing"),
        "decompilation-and-disassembly": (r"decompil", r"disassembl"),
        "cryptographic-implementation-analysis": (r"cryptographic implementation", r"crypto implementation analysis"),
        "unpacking-and-obfuscation-analysis": (r"unpack", r"deobfuscat", r"obfuscation analysis"),
    },
    "vulnerability-research": {
        "vulnerability-discovery": (r"vulnerability discovery", r"finding vulnerabilities", r"bug hunting"),
        "fuzzing-and-automated-testing": (r"fuzzing", r"fuzzer", r"automated testing"),
        "exploit-development": (r"exploit development", r"exploit research"),
        "zero-day-and-0-day-research": (r"zero[ -]?day", r"0day", r"0-day"),
        "cve-analysis-and-vulnerability-disclosure": (r"CVE-", r"vulnerability disclosure", r"security advisory"),
        "browser-and-web-platform-vulnerabilities": (r"browser vulnerability", r"web-platform vulnerability"),
        "kernel-and-operating-system-vulnerabilities": (r"kernel vulnerability", r"operating-system vulnerability"),
        "application-and-api-vulnerabilities": (r"application vulnerability", r"API vulnerability"),
        "mobile-vulnerabilities": (r"mobile vulnerability", r"Android vulnerability", r"iOS vulnerability"),
        "hardware-and-firmware-vulnerabilities": (r"hardware vulnerability", r"firmware vulnerability"),
        "iot-and-automotive-vulnerabilities": (r"IoT vulnerability", r"automotive vulnerability"),
        "protocol-and-network-vulnerabilities": (r"protocol vulnerability", r"network vulnerability"),
        "cryptographic-attacks": (r"cryptographic attack", r"crypto attack", r"side-channel", r"fault injection"),
        "exploit-mitigation-and-hardening": (r"exploit mitigation", r"hardening", r"security mitigation"),
        "bug-bounty-research": (r"bug bounty", r"bug-bounty"),
    },
    "identity-and-access-management": {
        "authentication": (r"authentication", r"login security"),
        "authorization-and-access-control": (r"authorization", r"access control"),
        "identity-lifecycle": (r"identity lifecycle", r"identity governance"),
        "directory-services": (r"Active Directory", r"LDAP", r"directory service"),
        "privileged-access-management": (r"privileged access", r"PAM"),
        "single-sign-on-and-federation": (r"single sign-on", r"SSO", r"federation"),
        "oauth-oidc-and-saml": (r"OAuth", r"OpenID", r"OIDC", r"SAML"),
        "credential-security": (r"credential security", r"password security", r"credential theft"),
    },
    "iot-security": {
        "embedded-devices": (r"embedded device", r"embedded security"),
        "smart-home-security": (r"smart home", r"home automation"),
        "consumer-iot-security": (r"consumer IoT", r"Internet of Things"),
        "device-onboarding-and-identity": (r"device onboarding", r"device identity"),
        "iot-protocols": (r"MQTT", r"Zigbee", r"Z-Wave", r"IoT protocol"),
        "iot-fleet-security": (r"IoT fleet", r"device fleet"),
    },
    "operational-technology-security": {
        "industrial-control-systems": (r"industrial control", r"\bICS\b"),
        "scada-security": (r"SCADA", r"SCADA security"),
        "plc-security": (r"\bPLC\b", r"PLC security"),
        "industrial-protocols": (r"Modbus", r"DNP3", r"industrial protocol"),
        "safety-systems": (r"safety system", r"safety instrumented"),
        "critical-infrastructure-resilience": (r"critical infrastructure", r"OT resilience"),
    },
    "threat-hunting": {
        "proactive-threat-hunting": (r"threat hunting", r"proactive hunting"),
        "hypothesis-driven-hunting": (r"hypothesis-driven", r"hunting hypothesis"),
        "endpoint-threat-hunting": (r"endpoint threat hunting", r"host threat hunting"),
        "network-threat-hunting": (r"network threat hunting", r"network hunting"),
        "cloud-threat-hunting": (r"cloud threat hunting", r"cloud hunting"),
        "identity-threat-hunting": (r"identity threat hunting", r"identity hunting"),
    },
}

_COMPILED_RULES = {
    domain: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for domain, patterns in _RULES.items()
}
_CANONICAL = {domain.casefold(): domain for domain in ALLOWED_DOMAINS}


def detect_domains(*values: Any) -> tuple[str, ...]:
    """Detect all matching cyber domains in deterministic taxonomy order."""

    text = " ".join(_flatten_text(value) for value in values if value is not None)
    detected = tuple(domain for domain in CYBER_DOMAINS if any(pattern.search(text) for pattern in _COMPILED_RULES[domain]))
    return detected or (UNKNOWN_DOMAIN,)


def detect_subspecialties(*values: Any, domains: Iterable[str] | None = None) -> dict[str, tuple[str, ...]]:
    """Detect normalized specialties, grouped under the detected domains."""

    text = " ".join(_flatten_text(value) for value in values if value is not None)
    selected = normalize_domains(domains) if domains is not None else detect_domains(*values)
    result: dict[str, tuple[str, ...]] = {}
    for domain in selected:
        matches = tuple(name for name, patterns in _SUBSPECIALTY_RULES.get(domain, {}).items() if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns))
        result[domain] = matches
    return result


def normalize_subspecialties(values: Mapping[str, Iterable[str]] | None, *, domains: Iterable[str]) -> dict[str, tuple[str, ...]]:
    """Canonicalize and validate a domain-keyed specialty mapping."""

    selected = normalize_domains(domains)
    if values is None:
        return {domain: () for domain in selected}
    if not isinstance(values, Mapping):
        raise DomainMappingError("subspecialties must be an object keyed by domains")
    if set(values) != set(selected):
        raise DomainMappingError("subspecialties keys must exactly match domains")
    normalized: dict[str, tuple[str, ...]] = {}
    for domain in selected:
        raw = values[domain]
        if isinstance(raw, str) or not isinstance(raw, Iterable):
            raise DomainMappingError(f"subspecialties.{domain} must be an array")
        names = tuple(dict.fromkeys(raw))
        known = _SUBSPECIALTY_RULES.get(domain, {})
        if any(not isinstance(name, str) or name not in known for name in names):
            raise DomainMappingError(f"Unsupported subspecialty in {domain}")
        normalized[domain] = tuple(name for name in known if name in names)
    return normalized


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
    specialties = record.get("subspecialties", {domain: [] for domain in values})
    normalized_specialties = normalize_subspecialties(specialties, domains=values)
    expected_specialties = {domain: list(names) for domain, names in normalized_specialties.items()}
    if specialties != expected_specialties:
        raise DomainMappingError(f"{source}.subspecialties must be canonical and keyed by domains")


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


