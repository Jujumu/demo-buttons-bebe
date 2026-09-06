"""Add explicit retained-content hints; never fetch TicketMessage.body_url."""

def curate_message(message):
    if not isinstance(message,dict):return message
    result=dict(message)
    preferred=next(((key,message[key]) for key in ('stripped_text','stripped_html','body_text','body_html')
                    if isinstance(message.get(key),str) and message[key].strip()),None)
    result['preferred_content']=preferred[1] if preferred else ''
    result['preferred_content_field']=preferred[0] if preferred else None
    result['content_unavailable']=preferred is None
    return result


def curate_messages(response):
    if isinstance(response,list):return [curate_message(message) for message in response]
    if isinstance(response,dict) and isinstance(response.get('data'),list):
        return {**response,'data':[curate_message(message) for message in response['data']]}
    return response


def curate_ticket(response):
    if isinstance(response,dict) and isinstance(response.get('messages'),list):
        return {**response,'messages':[curate_message(message) for message in response['messages']]}
    return response
