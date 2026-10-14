"""Pure authorization helpers for token-bound tool arguments."""

def validate_argument_constraints(tool, args, chain_constraints):
    for constraints in chain_constraints:
        rules = constraints.get(tool, {})
        domain = rules.get("to_domain")
        if domain:
            address = args.get("to", "")
            if not isinstance(address, str) or address.count("@") != 1 or address.rsplit("@", 1)[1].lower() != domain.lower():
                raise ValueError("argument violates recipient domain")
        allowed_ids = rules.get("allowed_ids")
        if allowed_ids is not None and args.get("id") not in allowed_ids:
            raise ValueError("argument violates id constraint")
    return True
