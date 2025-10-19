# Simple SMSC

A minimal, evolving **Short Message Service Center (SMSC)** implementation in Python.  
Currently focused on the **protocol stack** and **message handling** layers that form the foundation of a complete, SIP-based SMSC.

## Overview

**Simple SMSC** is a long-term project to build a standards-aligned SMSC that can send, receive, and route SMS messages using **SIP** (Session Initiation Protocol) as its transport layer.  
It will support both **SIP over TCP** and **SIP over WebSockets**, reflecting the transport mechanisms used in modern and emerging SMS infrastructure.

At this stage, development is concentrated on the lower layers — GSM and SMS protocol implementations. These define how SMS messages are encoded, parsed, and serialized according to GSM and 3GPP specifications.  
Future work will build upon this foundation to add SIP signaling, message routing, and delivery logic.

The design emphasizes clarity, testability, and conformance with open standards such as **GSM 03.40** and **`application/vnd.3gpp.sms`**.

## Key features

- Core protocol stack for GSM and SMS message handling  
- Parsing and serialisation with full `application/vnd.3gpp.sms` MIME support  
- Extensible architecture for SIP-based message transport (TCP and WebSocket)  
- Readable, modular Python implementation for development and experimentation  

## Status

| Area | Status | Description |
|------|---------|-------------|
| Protocol stack | ✅ Implemented | GSM/SMS message parsing, serialisation, and MIME support |
| Test coverage | ⚙️ In progress | Unit tests under development |
| SIP transport | 🧭 Planned | Support for SIP over TCP and SIP over WebSockets |
| SMSC core logic | 🧭 Planned | Message routing, store-and-forward, and delivery reports |
| Documentation | ⚙️ In progress | Internal architecture and protocol references |

## Project layout

- `packages/` — source code  
  - `protocol_lib/` — protocol handling layers  
    - `gsm/` — GSM message encoding/decoding and PDU utilities  
    - `sms/` — message models, parsing, and serialisation  
    - `utils/` — shared helpers for encoding, timestamps, and data conversion  

This structure isolates the low-level protocol logic from higher-level SIP and routing layers, allowing each component to evolve independently.

## Design goals

- **Transparency:** expose the internal structure of SMS and GSM message handling.  
- **Extensibility:** enable seamless integration of SIP (TCP/WebSocket) transport layers.  
- **Correctness:** adhere closely to GSM and 3GPP standards for message encoding and delivery.  
- **Simplicity:** maintain clear, approachable implementations throughout early development.  

## Roadmap

1. Finalize and validate GSM and SMS protocol layers  
2. Implement SIP transport over TCP and WebSockets  
3. Introduce message routing and store-and-forward logic  
4. Add delivery reports and message state tracking  
5. Develop CLI and test tools for full SMSC operation  

## License

MIT License — open for learning, research, and development.  
Contributions are welcome as the system evolves from a protocol suite into a complete, SIP-based SMSC.
See [`LICENSE` file](./LICENSE) for details.