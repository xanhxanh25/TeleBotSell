FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app
EXPOSE 5001
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["TokenPay/TokenPay.csproj", "TokenPay/"]
RUN dotnet restore "TokenPay/TokenPay.csproj"
COPY . .
WORKDIR "/src/TokenPay"
RUN dotnet build "TokenPay.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "TokenPay.csproj" -c Release -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "TokenPay.dll"]