"""What the language model must return for one form section (structured output).

Every value comes with the exact words it was read from. Nothing here is trusted: the validator
checks each quote against the passages sent and each value against its quotes.
"""

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMCitation(_Strict):
    passage: str = Field(description='Label of the quoted passage, as given: "P3".')
    quote: str = Field(
        description="Words copied exactly from that passage (a few words to one sentence) that "
        "state the value. Never paraphrased."
    )


class LLMDate(_Strict):
    date: str = Field(description="ISO date, YYYY-MM-DD.")
    citation: LLMCitation = Field(description="The words of the passage giving this date.")


class LLMCandidate(_Strict):
    value: str = Field(
        description="The answer to write in the field, made only of words found in its quotes. "
        'For a Yes/No field: "yes" or "no".'
    )
    citations: list[LLMCitation] = Field(
        description="One quote per fact the value is made of (usually one)."
    )
    source_date: LLMDate | None = Field(
        description="Date of the document or statement this value comes from (issue date, "
        "'as of' date), when the passages give it."
    )
    valid_until: LLMDate | None = Field(
        description="End of validity of the source (expiry of a certificate, policy period end), "
        "when the passages give it."
    )


class LLMFieldAnswer(_Strict):
    field: str = Field(description='The field\'s key exactly as given after "key:", e.g. "e_mail".')
    user_only: bool = Field(
        description="True when only the user can provide this by nature (place and date of "
        "signing, a personal choice): such fields are not searched in the documents."
    )
    user_only_reason: str | None = Field(
        description="Why only the user can fill it, in one short sentence for the user."
    )
    suggested_value: str | None = Field(
        description="For a user-only field, a value the user can confirm (e.g. the city of the "
        "registered office and today's date), or null."
    )
    candidates: list[LLMCandidate] = Field(
        description="The answer, as one candidate. Several only when sources disagree about the "
        "same fact, the most recent or most official first. Empty when the passages do not "
        "contain the answer: never guess."
    )


class LLMSectionAnswer(_Strict):
    fields: list[LLMFieldAnswer] = Field(description="One entry per field asked, in order.")
