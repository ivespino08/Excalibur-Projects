SUMMARY_PROMPT = """
        You will now create a summary of the findings that you discovered ONLY in the prompts since the last summary was requested. Findings are: \
            hosts that have been discovered, 
            services that are found on discovered hosts, 
            credentials found in hosts, 
            vulnerabilities that are identified on each host,
            any active or historical interactive sessions on discovered hosts.

        For each finding identified, you will create a the following JSON object:

            '''{

            "hosts":[
                {
                "ip_address": "The ip address of the host",
                "hostname": "The name of the host, if any, otherwise an empty string"
                }
            ],
            
            "services":[
                {
                "host_ip": "The ip_address of the host that the service was found on",
                "port": "The port number where the service is running, as an integer",
                "protocol": "tcp|udp",
                "service_name": "The name of the service",
                "version": "the version number of the service, if any, otherwise an empty string"
                }
            ],

            "credentials":[
                {
                "username": "username",
                "domain": "",
                "valid_for": ["a list of ip addresses for which the credentials are valid"],
                "credential_type": "password|hash|token|key",
                "credential_value": "the actual password|hash|token|key discovered"
                }
            ],

            "sessions":[
                {
                "host_ip": "The ip_address of the host that the session was found / created on",
                "session_type": "shell|meterpreter|ssh|rdp|winrm",
                "privilege_level": "user|admin|root|system",
                "active": true
                }
            ],

            "vulnerabilities":[
                {
                "host_ip": "The ip_address of the host that the vulnerability was found on",
                "service_name": "the name of the service where the vulnerability was found, if any, otherwise an empty string",
                "cve_id": "The cve id relating to the vulnerability, if any, otherwise an empty string",
                "description": "A small description of the vulnerability and how it was found",
                "exploitation_status": "discovered|attempted|exploited|failed"
                }
            ]
            }'''

        The summary should be a JSON object that contains 5 lists of JSON object - one for each type of finding.
        

        Restrictions:
            DO NOT perform any actions other that creating this summary.
            Use ONLY information you already have available, DO NOT explore or exploit further to create more findings.
            Use only information that has been discovered since the last time a summary was created.
            There should be ABSOLUTELY NO other text in the response aside from the JSON object.
            DO NOT explain what you are doing, only produce the JSON object.
            ABSOLUTELY DO NOT USE BACKTICKS. The JSON object must be Python compatible.
            "active" must be a real JSON boolean (true or false, no quotes), not a string.
"""