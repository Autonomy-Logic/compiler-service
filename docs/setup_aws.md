# AWS Setup Instructions
This document provides step-by-step instructions for setting up the application on an EC2 AWS instance.

## Prerequisites
- An AWS account with permissions to create and manage EC2 instances.
- Basic knowledge of AWS services and Linux command line.
- SSH client to connect to the EC2 instance.

## Step 1: Install compiler-service and test locally on your EC2 instance
1. Clone the repository:
   ```bash
   git clone https://github.com/autonomy-logic/compiler-service.git
   ```
2. Navigate to the project directory:
   ```bash
   cd compiler-service
   ```
3. Install:
   ```bash
   sudo ./install.sh
   ```
4. Run the application locally:
   ```bash
   start_local.sh
   ```
5. Test the application using curl:
    ```bash
    curl -X POST http://localhost:8000/generate-st \
    -H "Content-Type: application/json" \
    -d "{\"plc_xml\": \"$(cat input.xml | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])')\"}"
    ```
    Make sure to replace `input.xml` with the path to your actual PLC XML file.

## Step 2: Configure gunicorn + nginx
1. Create a systemd service file for gunicorn:
    ```bash
    sudo nano /etc/systemd/system/compiler.service
    ```
    Add the following content:
    ```ini
    [Unit]
    Description=Gunicorn service for OpenPLC XML2ST
    After=network.target

    [Service]
    User=ec2-user
    Group=ec2-user
    WorkingDirectory=/home/ec2-user/compiler-service
    Environment="PATH=/home/ec2-user/compiler-service/venv/bin"
    ExecStart=/home/ec2-user/compiler-service/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b unix:/home/ec2-user/compiler-service/compiler.sock app.main:app

    [Install]
    WantedBy=multi-user.target
    ```

2. Reload systemd and start the service:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start compiler.service
    sudo systemctl enable compiler.service
    ```

3. Configure nginx as a reverse proxy:
    ```bash
    sudo nano /etc/nginx/conf.d/compiler.conf
    ```
    Add the following content:
    ```nginx
    server {
        listen 80;
        server_name [your_domain] www.[your_domain];

        location / {
            proxy_pass http://unix:/home/ec2-user/compiler-service/compiler.sock;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
    ```

4. Make sure nginx can access gunicorn socket:
    ```bash
    sudo chmod 666 /home/ec2-user/compiler-service/compiler.sock
    sudo chmod 755 /home
    sudo chmod 755 /home/ec2-user
    sudo chmod 755 /home/ec2-user/compiler-service
    ```

5. Test nginx configuration and restart nginx:
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```

    Note: Make sure your EC2 instance's security group allows inbound traffic on port 80 (HTTP) to access the application from the internet.

6. Configure Domain
    - Go to the domain registrar's website
    - Create the following DNS record:
        - Type: A
        - Name: @
        - Value: [Your EC2 Instance Public IP]
        - TTL: 1 Hour
    - Create another DNS record:
        - Type: CNAME
        - Name: www
        - Value: [Your EC2 Instance Public IP]
        - TTL: 1 Hour

## Step 3: Secure the application with SSL
1. Install Certbot:
    ```bash
    sudo yum install certbot python3-certbot-nginx -y
    ```

2. Obtain and install SSL certificate:
    ```bash
    sudo certbot --nginx -d [your_domain] -d www.[your_domain]
    ```

3. Follow the prompts to complete the SSL installation. Certbot will automatically configure nginx to use the new certificates.