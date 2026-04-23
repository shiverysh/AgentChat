from agentchat.tools.send_email.action import send_email
from agentchat.tools.web_search.google_search.action import google_search
from agentchat.tools.web_search.tavily_search.action import tavily_search
from agentchat.tools.web_search.bocha_search.action import bocha_search
from agentchat.tools.arxiv.action import get_arxiv
from agentchat.tools.get_weather.action import get_weather
from agentchat.tools.delivery.action import get_delivery_info
from agentchat.tools.text2image.action import text_to_image
from agentchat.tools.docx_to_pdf.action import convert_to_pdf
from agentchat.tools.pdf_to_docx.action import convert_to_docx
from agentchat.tools.image2text.action import image_to_text
from agentchat.tools.mineru_parse.action import mineru_parse
from agentchat.tools.resume_match.action import resume_match
from agentchat.tools.resume_rewrite.action import resume_rewrite
from agentchat.tools.interview_followup.action import interview_followup


AgentTools = [
    send_email,
    tavily_search,
    bocha_search,
    get_weather,
    get_arxiv,
    get_delivery_info,
    text_to_image,
    image_to_text,
    mineru_parse,
    convert_to_pdf,
    convert_to_docx,
    resume_match,
    resume_rewrite,
    interview_followup,
]


AgentToolsWithName = {
    "send_email": send_email,
    "tavily_search": tavily_search,
    "web_search": tavily_search,
    "get_arxiv": get_arxiv,
    "get_weather": get_weather,
    "get_delivery_info": get_delivery_info,
    "get_delivery": get_delivery_info,
    "text_to_image": text_to_image,
    "image_to_text": image_to_text,
    "mineru_parse": mineru_parse,
    "docx_to_pdf": convert_to_pdf,
    "convert_to_pdf": convert_to_pdf,
    "pdf_to_docx": convert_to_docx,
    "convert_to_docx": convert_to_docx,
    "bocha_search": bocha_search,
    "resume_match": resume_match,
    "resume_rewrite": resume_rewrite,
    "interview_followup": interview_followup,
}

WorkSpacePlugins = AgentToolsWithName

LingSeekPlugins = AgentToolsWithName

WeChatTools = {
    "tavily_search": tavily_search,
    "get_arxiv": get_arxiv,
    "get_weather": get_weather,
    "text_to_image": text_to_image,
    "bocha_search": bocha_search,
}
