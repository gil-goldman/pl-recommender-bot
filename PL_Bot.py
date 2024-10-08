# Set up imports
import streamlit as st
import requests
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState, START, END  
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, SystemMessage  
import os
from dotenv import load_dotenv

# Import the system prompt from the system_prompt.py file
from system_prompt import system_prompt

# Load environment variables
load_dotenv()
os.environ["ANTHROPIC_API_KEY"] = os.getenv("CLAUDE_KEY")

# Initialize Claude with tool bindings
claude = ChatAnthropic(model="claude-3-5-sonnet-20240620")

# Define GraphQL API call
def call_graphql_api(principal, tenure):
    """Calls GraphQL API to fetch personal loan options based on principal and tenure using a predefined query ID."""
    print("Called call_graphql_api with:", principal, tenure)
    
    # Use the predefined query ID from the sample
    query_id = "497647c4e5718076f21a6962bbdc37ce8afd6572e571cfa6a54b132e79ce134e"
    
    variables = {
        "productUids": [
            "SG.PL.TRB.TRUST-PERSONAL-LOAN",
            "SG.PL.CIMB.CIMB-PERSONAL-LOAN",
            "SG.PL.UOB.UOB-PERSONAL-LOAN",
            "SG.PL.SCB.SCB-CASHONE-PERSONAL-LOAN",
            "SG.PL.HSBC.HSBC-PERSONAL-LOAN",
            "SG.PL.GXS.GXS-FLEXILOAN",
            "SG.PL.CRED.CREDIBLE-PERSONAL-LOAN",
            "SG.PL.DBS.DBS-PERSONAL-LOAN",
            "SG.PL.POSB.POSB-PERSONAL-LOAN"
        ],
        "input": {
            "tenureInMonths": str(tenure),
            "principalAmount": str(principal)
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(
        url='https://www.singsaver.com.sg/api/gql',
        json={"id": query_id, "variables": variables},
        headers=headers
    )
    
    # Log status code and full response
    print(f"Received response, status code: {response.status_code}")
    print("Response body:", response.text)
    
    if response.status_code == 200:
        data = response.json()
        return data['data']
    else:
        return f"Error: {response.status_code}, {response.text}"

# Define the tool function for loan recommendation
def fetch_loans(principal, tenure):
    """Fetches loan options based on the user's principal and tenure."""
    print(f"Triggered fetch_loans with principal: {principal} and tenure: {tenure}")
    result = call_graphql_api(principal, tenure)
    print("GraphQL API result:", result)
    
    if result:
        return {
            "messages": [{
                "content": f"Here are some loan options based on your input for principal: {principal} and tenure: {tenure}",
                "tool_calls": result  # Populate with GraphQL result
            }]
        }
    else:
        return {
            "messages": [{
                "content": "Failed to fetch loan options. Please try again."
            }]
        }

# Now we add this tool to a ToolNode
tools = [fetch_loans]

# Log tool binding process
print("Binding Claude with tools...")
tool_node = ToolNode(tools)  # No need for decorator, pass tools like this
model = claude.bind_tools(tools)
print("Claude is now bound with tools")

# Define the function to decide next step (continue or use tools)
def should_continue(state: MessagesState) -> str:
    if state['messages'][-1].tool_calls:
        return "tools"
    return END

# Function to invoke model (Claude) and process the user message
# Add the system message to the state
def call_model(state: MessagesState):
    # Ensure the system prompt is only added once
    if not any(isinstance(msg, SystemMessage) for msg in state['messages']):
        state['messages'].insert(0, SystemMessage(content=system_prompt))
    
    # Invoke the model with the system prompt and user message
    response = model.invoke(state['messages'])
    return {"messages": [response]}

# Define the graph
workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, ["tools", END])
workflow.add_edge("tools", "agent")

# Streamlit interface for user input
st.title("Loan Recommender Chatbot")

if 'chat_state' not in st.session_state:
    st.session_state['chat_state'] = {"messages": []}

user_input = st.text_input("You:", "")

# Handle the chat
if user_input:
    st.session_state['chat_state']["messages"].append(HumanMessage(content=user_input))
    
    # Compile the graph after building it
    compiled_graph = workflow.compile()

    # Process the conversation via the graph
    try:
        final_state = compiled_graph.invoke(st.session_state['chat_state'])
        response = final_state["messages"][-1].content
    except Exception as e:
        response = f"An error occurred: {e}"
        print("Error during tool call:", e)
    
    st.markdown(f"Rebecca: {response}")