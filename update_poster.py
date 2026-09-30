import re

with open('poster.tex', 'r') as f:
    content = f.read()

# 1. Fix Header
header_replacement = r"""\setbeamertemplate{headline}{
  \leavevmode
  \begin{columns}[c]
    \begin{column}{.1\paperwidth}
    \end{column}
    \begin{column}{.75\paperwidth}
      \vskip2.5cm
      \centering
      \usebeamercolor{title in headline}{\color{fg}\textbf{\fontsize{90}{110}\selectfont \inserttitle}\\[2ex]}
      \vskip1cm
      \usebeamercolor{author in headline}{\color{fg}\LARGE{\textbf{\insertauthor}}\\[1.5ex]}
      \usebeamercolor{institute in headline}{\color{fg}\Large{\insertinstitute}\\[1ex]}
      \vskip1.5cm
    \end{column}
    \begin{column}{.15\paperwidth}
      \centering
      \includegraphics[width=0.8\linewidth,keepaspectratio]{logo.jpeg}
    \end{column}
  \end{columns}
  \vskip1cm
}"""
content = re.sub(r'\\setbeamertemplate\{headline\}\{.*?\\setbeamertemplate\{footline\}', header_replacement + '\n\\setbeamertemplate{footline}', content, flags=re.DOTALL)

# 2. Rewrite Columns and Blocks
# We will just replace everything between \begin{columns}[T] and \end{columns} (at the end of frame)
body_replacement = r"""\begin{columns}[T]

% ==================== COLUMN 1 ====================
\begin{column}{.31\paperwidth}

\begin{block}{Problem Statement: The Deepfake Threat}
\begin{minipage}[t][28cm][c]{\linewidth}
    \vspace{0.5cm}
    \begin{itemize}
        \item[\textcolor{neoncyan}{\textbf{>}}] \Large \textbf{The Context:} Synthetic media threatens digital finance, public discourse, and identity security in Bangladesh.
        \vspace{0.5cm}
        \item[\textcolor{neoncyan}{\textbf{>}}] \Large \textbf{The Challenge:} Standard security protocols fail against advanced AI threats like MFS e-KYC bypass and political misinformation.
    \end{itemize}
    \vspace{1cm}
    \begin{center}
    \resizebox{0.75\linewidth}{!}{
        \begin{tikzpicture}[node distance=1.5cm and 2cm]
            \node (df) [circle, draw=neonmagenta, fill=bgblock, text=white, very thick, minimum size=5cm, align=center, drop shadow] {\Huge \textbf{DEEPFAKES}};
            \node (threat1) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=6cm, minimum height=2cm, align=center, above right=of df, xshift=1cm] {\LARGE \textbf{Financial Fraud}};
            \node (threat2) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=6cm, minimum height=2cm, align=center, right=of df, xshift=2cm] {\LARGE \textbf{Misinformation}};
            \node (threat3) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=6cm, minimum height=2cm, align=center, below right=of df, xshift=1cm] {\LARGE \textbf{Identity Theft}};
            
            \draw [arrow, neonmagenta] (df) -- (threat1);
            \draw [arrow, neonmagenta] (df) -- (threat2);
            \draw [arrow, neonmagenta] (df) -- (threat3);
        \end{tikzpicture}
    }
    \end{center}
\end{minipage}
\end{block}

\vspace{1.5cm}

\begin{block}{The Deep Learning Solution}
\begin{minipage}[t][20cm][c]{\linewidth}
    \begin{center}
    \resizebox{0.85\linewidth}{!}{
        \begin{tikzpicture}[node distance=1.5cm and 1cm]
            \node (cnn) [rectangle, draw=neongreen, fill=bgblock, text=white, very thick, minimum width=10cm, minimum height=3cm, align=center, drop shadow] {\Huge \textbf{Transformer-Based Model}};
            \node (adv1) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=5cm, minimum height=2cm, align=center, below left=1.5cm and -2cm of cnn] {\Large \textbf{Automated Detection}};
            \node (adv2) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=5cm, minimum height=2cm, align=center, below=2cm of cnn] {\Large \textbf{Sub-pixel Precision}};
            \node (adv3) [rectangle, draw=neoncyan, fill=bgdark, text=white, very thick, minimum width=5cm, minimum height=2cm, align=center, below right=1.5cm and -2cm of cnn] {\Large \textbf{100\% Local/Secure}};
            
            \draw [arrow, neongreen] (cnn) -- (adv1);
            \draw [arrow, neongreen] (cnn) -- (adv2);
            \draw [arrow, neongreen] (cnn) -- (adv3);
        \end{tikzpicture}
    }
    \end{center}
\end{minipage}
\end{block}

\end{column}

% ==================== COLUMN 2 ====================
\begin{column}{.31\paperwidth}

\begin{block}{Neural Architecture}
\begin{minipage}[t][28cm][c]{\linewidth}
    \begin{center}
        \includegraphics[height=25cm,keepaspectratio]{sleek_diagram.jpg}
    \end{center}
\end{minipage}
\end{block}

\vspace{1.5cm}

\begin{block}{AI Inference Pipeline}
\begin{minipage}[t][20cm][c]{\linewidth}
    \begin{center}
    \resizebox{0.85\linewidth}{!}{
        \begin{tikzpicture}[node distance=1.5cm and 2cm]
            \node (in) [io] {\textbf{Video Input} \\ (Raw Stream)};
            \node (sample) [process, below=of in] {\textbf{Frame Extraction} \\ (12 Distinct Frames)};
            \node (nn) [process, below=of sample] {\textbf{Transformer Model} \\ (Feature Extraction)};
            \node (agg) [process, below=of nn] {\textbf{Sigmoid Activation} \\ (Probability Score)};
            \node (dec) [decision, below=of agg] {\textbf{Mean} \\ $> 0.50$?};
            
            \node (fake) [io, right=of dec, draw=techred, text=techred, xshift=1cm] {\huge \textbf{SYNTHETIC}};
            \node (real) [io, left=of dec, draw=neongreen, text=neongreen, xshift=-1cm] {\huge \textbf{AUTHENTIC}};
            
            \draw [arrow] (in) -- (sample);
            \draw [arrow] (sample) -- (nn);
            \draw [arrow] (nn) -- (agg);
            \draw [arrow] (agg) -- (dec);
            \draw [arrow, techred] (dec) -- node[anchor=south, yshift=0.2cm, text=titletext] {\LARGE \textbf{Yes}} (fake);
            \draw [arrow, neongreen] (dec) -- node[anchor=south, yshift=0.2cm, text=titletext] {\LARGE \textbf{No}} (real);
        \end{tikzpicture}
    }
    \end{center}
\end{minipage}
\end{block}

\end{column}

% ==================== COLUMN 3 ====================
\begin{column}{.31\paperwidth}

\begin{block}{Artifact Detection \& Localization}
\begin{minipage}[t][28cm][c]{\linewidth}
    \begin{center}
        \includegraphics[height=18cm,keepaspectratio]{sleek_concept.jpg}\hspace{1cm}
        \includegraphics[height=18cm,keepaspectratio]{heatmap.jpg}
    \end{center}
    \vspace{1cm}
    \centering \Large \textit{Unlike macroscopic facial analysis, our Transformer-based model targets subtle spatial-temporal inconsistencies and boundary warping where generators fail.}
\end{minipage}
\end{block}

\vspace{1.5cm}

\begin{block}{Impact \& Future Scope}
\begin{minipage}[t][20cm][c]{\linewidth}
    \begin{itemize}
        \item[\textcolor{neoncyan}{\textbf{>}}] \Large \textbf{Lightweight Model:} Resource-efficient proprietary model for mobile edge devices.
        \vspace{1cm}
        \item[\textcolor{neoncyan}{\textbf{>}}] \Large \textbf{Localized Threats:} Combating MFS e-KYC bypass, official impersonation, and fraudulent loans.
        \vspace{1cm}
        \item[\textcolor{neoncyan}{\textbf{>}}] \Large \textbf{Multimodal Expansion:} Fusing audio-video analysis to detect coordinated scams.
    \end{itemize}
\end{minipage}
\end{block}

\end{column}

\end{columns}"""

content = re.sub(r'\\begin\{columns\}\[T\].*?\\end\{columns\}', body_replacement, content, flags=re.DOTALL)

with open('poster.tex', 'w') as f:
    f.write(content)
