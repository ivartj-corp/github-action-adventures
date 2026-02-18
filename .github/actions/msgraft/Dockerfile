FROM mcr.microsoft.com/powershell@sha256:810c4f1e0c9d23022c3ec18c50a6205ee4b60766f1739d329b2948df1fd7d5b0

ARG MSGRAPH_VERSION=2.28.0

RUN pwsh -c Install-Module -Force -RequiredVersion $MSGRAPH_VERSION -Scope AllUsers Microsoft.Graph.Authentication
RUN pwsh -c Install-Module -Force -RequiredVersion $MSGRAPH_VERSION -Scope AllUsers Microsoft.Graph.Applications
RUN pwsh -c Install-Module -Force -RequiredVersion $MSGRAPH_VERSION -Scope AllUsers Microsoft.Graph.Groups
RUN pwsh -c Install-Module -Force -RequiredVersion $MSGRAPH_VERSION -Scope AllUsers Microsoft.Graph.DirectoryObjects

COPY entrypoint.ps1 /entrypoint.ps1

ENTRYPOINT [ "/opt/microsoft/powershell/7/pwsh", "-c", "/entrypoint.ps1" ]
