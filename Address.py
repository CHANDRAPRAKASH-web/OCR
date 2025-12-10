# find contiguous address block starting from any address hint near bottom
        address_lines = []
        if structured_lines:
            # find lines that look like address hints
            address_hints = [ln for ln in structured_lines if ln.get("is_address_hint")]
            if address_hints:
                # pick the lowest hint (highest idx)
                anchor = max(address_hints, key=lambda x: x.get("idx", 0))
                i = anchor.get("idx", None)
                # guard: ensure i is a valid index in structured_lines
                if i is None:
                    i = None
                else:
                    try:
                        i = int(i)
                    except Exception:
                        i = None

                if i is not None and 0 <= i < len(structured_lines):
                    # expand upward from anchor while staying in bounds
                    j = i
                    added = 0
                    while j >= 0 and added < 6:   # limit safety: do not loop forever; max 6 lines
                        ln = structured_lines[j]
                        # stop expansion if line is clearly contact info (email/phone/website)
                        if ln.get("is_contact"):
                            break
                        text = (ln.get("text") or "").strip()
                        # skip empty or nonsense lines, but allow a single short gap
                        if text == "":
                            j -= 1
                            continue
                        # insert at front (we're moving upward)
                        address_lines.insert(0, text)
                        added += 1
                        j -= 1

                    # also try to expand downward a little to capture trailing address lines
                    k = i + 1
                    added_down = 0
                    while k < len(structured_lines) and added_down < 4:
                        ln2 = structured_lines[k]
                        if ln2.get("is_contact"):
                            break
                        t2 = (ln2.get("text") or "").strip()
                        if t2 == "":
                            k += 1
                            continue
                        address_lines.append(t2)
                        added_down += 1
                        k += 1
                else:
                    # anchor idx invalid — fallback: try to pick the last few lines that look like addresses
                    candidates = [ln.get("text","").strip() for ln in structured_lines if ln.get("is_address_hint")]
                    # take last up to 3 hints as fallback
                    if candidates:
                        address_lines = candidates[-3:]
