def escape_bad_html(text):
    # text = text.replace('&', '&#38;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text
