import chainlit as cl
import time
import logging
from chainlit.input_widget import Select
from functions import (
    get_sql_query,
    run_query,
    detect_delay_unit,
    call_llm,
    is_delay_query,
    route_question,
    build_context_note,
)
from prompts import EXPLANATION_PROMPT

PROVIDER_DISPLAY_NAMES = {
    "groq": "Groq API",
    "llama": "Llama3",
}

SUGGESTED_QUESTIONS = [
    ("Average delay for a line", "What is the average delay in minutes for route IC?"),
    ("On-time percentage", "What percentage of trains are on time for route S8?"),
    ("Worst platform at a station", "Which platform at Brussels-Central has the worst average delay?"),
    ("Compare delays across lines", "Which train line has the most total delayed minutes?"),
]

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label=label, message=question)
        for label, question in SUGGESTED_QUESTIONS
    ]
 
 
async def process_question(question: str):
    """
    Core pipeline: routing -> (SQL generation -> execution) or (direct followup)
    -> consultant reformulation -> history update -> send the reply.
 
    Shared by both entry points: a typed message (@cl.on_message) and a
    clicked suggested-question button (@cl.action_callback) -- avoids
    duplicating this whole flow in two places.
    """
    debut = time.time()
    provider = cl.user_session.get("provider")
    sql_history = cl.user_session.get("sql_history")
    chat_history = cl.user_session.get("chat_history")
 
    decision = route_question(question, chat_history, provider)
 
    if decision == "SQL_NEEDED":
        try:
            async with cl.Step(name="sql query") as step1:
                context_note = build_context_note(chat_history)
                sql_query = get_sql_query(question + context_note, provider, history=sql_history)
                step1.output = sql_query
 
            async with cl.Step(name="run query") as step2:
                answer = run_query(sql_query)
                step2.output = str(answer)
        except Exception as e:
            logging.error(f"Failed to process question '{question}': {e}")
            await cl.Message(
                content="I couldn't process that question — could you rephrase it?"
            ).send()
            return
 
        async with cl.Step(name="response") as step3:
            prompt_message = f"User question: {question}\nQuery results: {answer}"
            if is_delay_query(sql_query):
                units = detect_delay_unit(sql_query)
                prompt_message += f", The delay values above are already expressed in {units}."
 
            response = call_llm(EXPLANATION_PROMPT, prompt_message, provider, history=chat_history)
            fin = time.time()
            duree = fin - debut
            step3.output = f"Response generated ({len(response)} characters in {duree:.2f} seconds)"
 
        sql_history.append({"role": "user", "content": question})
        sql_history.append({"role": "assistant", "content": sql_query})
        cl.user_session.set("sql_history", sql_history)
 
    else:  # FOLLOWUP
        async with cl.Step(name="response") as step3:
            response = call_llm(EXPLANATION_PROMPT, question, provider, history=chat_history)
            fin = time.time()
            duree = fin - debut
            step3.output = f"Response generated ({len(response)} characters in {duree:.2f} seconds)"
 
    chat_history.append({"role": "user", "content": question})
    chat_history.append({"role": "assistant", "content": response})
    cl.user_session.set("chat_history", chat_history)
 
    author = PROVIDER_DISPLAY_NAMES.get(provider, "RailPulse") 
    await cl.Message(content=response, author=author).send()
    
    
@cl.on_chat_start
async def start():
    await cl.ChatSettings(
        [
            Select(
                id="Model",
                label="LLM - Provider",
                values=["groq", "llama"],
                initial_index=0,
            ),
        ]
    ).send()
 
    cl.user_session.set("sql_history", [])
    cl.user_session.set("chat_history", [])
    cl.user_session.set("provider", "groq")
 
    display_name = PROVIDER_DISPLAY_NAMES.get("groq", "groq")
    actions = [
        cl.Action(name="ask_question", label=label, payload={"question": question})
        for label, question in SUGGESTED_QUESTIONS
    ]
    await cl.Message(
        content=f"Welcome to RailPulse! Currently using **{display_name}**.\n\n"
                f"Try one of the suggestions below, or type your own question.",
        actions=actions,
    ).send()
 
 
@cl.on_settings_update
async def setup_agent(settings):
    provider = settings["Model"]
    cl.user_session.set("provider", provider)
    display_name = PROVIDER_DISPLAY_NAMES.get(provider, provider)
    await cl.Message(content=f"Now using **{display_name}**").send()
 
 
@cl.action_callback("ask_question")
async def on_action(action: cl.Action):
    question = action.payload["question"]
    await process_question(question)
 
 
@cl.on_message
async def main(message: cl.Message):
    await process_question(message.content)
 