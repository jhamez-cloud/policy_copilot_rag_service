'''Documentation String'''
from .retrieval import Hit

SYSTEM_PROMPT = (
    "You are PolicyCopilot, an assistant that answers employee questions "
    "about company policies. Answer only from the policies provided in the "
    "user's message. If the policies don't contain the answer, say so "
    "plainly instead of guessing. Mention the policy name you are relying "
    "on, and include any limits, deadlines, or approval requirements."
)

def augment_user_prompt(question:str,hits:list[Hit]) -> str:
    '''Documentation String'''

    context = "\n\n".join(
        f"Source {i}: {hit.title}\n{hit.text}" for i,hit in enumerate(hits,1)
    )

    augmented_prompt = f"POLICIES:\n    {context}\n\nQUESTION:\n    {question}"

    return augmented_prompt
