# **Plan B: Market Research Feature \- Functional Requirements & Design Specification**

This document outlines the design, architecture, and functional requirements for the "Market Research" feature within the Plan B ecosystem. This tool is designed to automate comprehensive market analysis by leveraging parallel Large Language Model (LLM) processing, Retrieval-Augmented Generation (RAG), and a multi-stage review system.

## **1\. User Interface Design**

The user interface will be integrated as a dedicated tab ("Market Reasearch") within the existing **Strategy Room** of the Plan B Administration application.

* **Market Research Tab:** A separate navigation element to isolate research workflows from other strategy tools.  
* **Control Panel:**  
  * **Research Topic Input:** A primary text area for defining the research prompt.  
  * **File Upload:** A drag-and-drop zone for supplementary documents (PDFs, text files) to be processed into RAG.  
  * **LLM Selector:** A checklist or grid allowing the user to select specific models to participate in the research cycle. LLM's available for market research will be determined by the available API key's in the environment. By default, OpenAI, Gemini & Claude should always be available. 
  * **Critic Highlight:** A visual indicator (e.g., a colored border or badge) identifying which model is designated as the 'Critic' for final reflection. if Grok is available, it will be assigned the critic role by default. This assignment can be edited by the user. 
* **Status & Monitoring:** A progress bar or real-time status indicators showing the current state of each parallel model (e.g., "Gathering Data," "Merging," "Reflecting").

## **2\. Functional Requirements**

The system must fulfill the following core functions:

| Requirement ID | Description   |
| :---- | :---- |
| FR-01 | **Prompt Optimization:** The system shall take the initial user prompt and utilize a specialized LLM to generate optimized instructions for research and review models. |
| FR-02 | **RAG Integration:** Uploaded files must be parsed, vectorized, and stored in a Retrieval-Augmented Generation database for retrieval by research nodes. |
| FR-03 | **Parallel Execution:** Research models must execute concurrently, each focusing on unique aspects (e.g., competition, market size). |
| FR-04 | **Merging & Synthesis:** A central model shall merge individual research results into a cohesive, structured report. |
| FR-05 | **PDF Export & Storage:** The finalized report must be converted to PDF format and automatically uploaded to the user's Google Drive. |

## **3\. Data Flow & System Architecture**

The architectural flow follows a linear progression with a feedback loop at the final stage:

1. **Input Layer:** User provides a research prompt and optional files via the Web Interface.  
2. **Preprocessing:**  
   * **RAG Storage:** Documents are converted and stored.  
   * **Prompt Optimizer:** The user prompt is refined into technical instructions for each agent. Final user prompts will be visible to the user in "Market Research" page.
3. **Research Tier:** Multiple LLMs trigger in parallel, querying both public data and the internal RAG database.  
4. **Synthesis Tier:** A "Merging Model" combines outputs, ensuring logical flow and removing redundancies.  
5. **Reflection Tier (Review & Reflection):** The 'Critic' node reviews the merged report for quality, missing information, or contradictions. Feedback can be passed back to the planner if gaps are identified.  
6. **Output Tier:** A Python service generates a PDF and interfaces with the Google Drive API for storage.

## **4\. Detailed Workflow: Review and Reflection**

The Critic node acts as the "Review and Reflection" layer. This step is critical for ensuring that the final output is not just a collection of data, but a verified analysis. This node evaluates:

* **Consistency:** Do the data points from different models contradict each other?  
* **Completeness:** Were all parts of the initial optimized prompt addressed?  
* **Actionability:** Does the report provide clear insights for the Plan B strategy?

## **5\. Technical Stack Considerations**

* **Backend:** Python for RAG orchestration and PDF generation.  
* **APIs:** Google Drive API for file storage.  
* **Models:** Flexible selection of LLMs (e.g., GPT-4, Claude 3, Gemini) as defined by the user in the UI.