#include <arpa/inet.h>
#include <errno.h>
#include <getopt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define CLIENT_MSG_SIZE 5000

#ifndef BUF_SIZE
#define BUF_SIZE 500
#endif

#ifndef DUMMY_SIZE
#define DUMMY_SIZE 0
#endif

typedef struct info {
    int   level;
    int   port;
    char *bind_addr;
    int   buf_low;
    int buf_high;
    int   addr_mask;
    int   print_hint;
} info;

// BUF_SIZE defined on compile

//function has buffer-overflow vulnerability
void bof(char *str, struct info *args);
//Initialize the TCP socket
int init_tcp_server(struct info *args);
//Read input sent by client
int read_client_data(int client_sock, struct info *args);
//Server listens to TCP connection
int run_server(int socket_desc, struct info *args);
//Functions to send Hint to Daemon
void sendHint(const void *buffer, uintptr_t framep, struct info *args);

int main(int argc, char *argv[]) {
    char dummy[DUMMY_SIZE]; // dummy array to offset ebp.
    struct info args;
    args.level      = -1;
    args.port       = -1;
    args.bind_addr  = NULL;
    args.buf_low  = -1;
    args.buf_high    = -1;
    args.addr_mask  = -1;
    args.print_hint = 1;

    int socket_desc;
    int opt;

    while ((opt = getopt(argc, argv, "l:p:b:s:S:m:")) != -1) {
        switch (opt) {
            case 'l': args.level = atoi(optarg); break;
            case 'p': args.port = atoi(optarg); break;
            case 'b': args.bind_addr = optarg; break;
            case 's': args.buf_low = atoi(optarg); break;
            case 'S': args.buf_high = atoi(optarg); break;
            case 'm': sscanf(optarg, "0x%08X", &args.addr_mask); break;
            default: /* '?' */
                fprintf(stderr,
                        "Usage: %s -l level -p port -b bind address -s buffer "
                        "size low -S buffer size high -m address mask\n",
                        argv[0]);
                return -1;
        }
    }

    switch (args.level) {
        case 1:
        case 4:
            if (args.port == -1 || args.bind_addr == NULL) {
                fprintf(stderr, "err#Argument Parsing Failed\n");
                return -1;
            }
            break;
        case 2:
            if (args.port == -1 || args.bind_addr == NULL
                || args.buf_low == -1 || args.buf_high == -1) {
                fprintf(stderr, "err#Argument Parsing Failed\n");
                return -1;
            }
            break;
        case 3:
            if (args.level == -1 || args.port == -1 || args.bind_addr == NULL
                || args.buf_low == -1 || args.buf_high == -1
                || args.addr_mask == -1) {
                fprintf(stderr, "err#Argument Parsing Failed\n");
                return -1;
            }
            break;
        default: fprintf(stderr, "err#Argument Parsing Failed\n"); return -1;
    }

    socket_desc = init_tcp_server(&args);
    if (socket_desc == -1) return -1;

    while (run_server(socket_desc, &args) != 0) continue;

    return 0;
}

int init_tcp_server(struct info *args) {
    int                socket_desc;
    struct sockaddr_in server;
    //Create socket
    socket_desc = socket(AF_INET, SOCK_STREAM, 0);
    if (socket_desc == -1) {
        fprintf(stderr, "err#Create Socket Failed\n: %s", strerror(errno));
        return -1;
    }

    //Prepare the sockaddr_in structure
    server.sin_family = AF_INET;
    inet_aton(args->bind_addr, &server.sin_addr);
    server.sin_port = htons(args->port);
    int tr          = 1;

    if (setsockopt(socket_desc, SOL_SOCKET, SO_REUSEADDR, &tr, sizeof(int))
        != 0) {
        fprintf(stderr, "err#Set Socket Option Failed\n: %s", strerror(errno));
        return -1;
    }

    //Bind socket to address
    if (bind(socket_desc, (struct sockaddr *)&server, sizeof(server)) != 0) {
        fprintf(stderr, "err#Bind Failed\n: %s", strerror(errno));
        return -1;
    }

    return socket_desc;
}

int read_client_data(int client_sock, struct info *args) {
    char client_message[CLIENT_MSG_SIZE];
    int  read_size;
    int  index = 0;

    memset(client_message, 0, CLIENT_MSG_SIZE);

    //Receive a message from client
    while ((read_size = recv(client_sock, client_message + index,
                             CLIENT_MSG_SIZE - index, 0))
           > 0) {
        index += read_size;
    }

    //DumpHex(client_message, index);

    if (read_size == -1) {
        //fprintf(stderr, "err#Data Receive Failed\n: %s", strerror(errno));
        return -1;
    }

    fprintf(stdout, client_message, index);
    fflush(stdout);
    //vulnerable function
    bof(client_message, args);

    //Send the message back to client
    write(client_sock, client_message, index);

    return 0;
}

int run_server(int socket_desc, struct info *args) {
    int                client_sock, c;
    struct sockaddr_in client;
    int                pid;

    // handle signal from child processes
    signal(SIGCHLD, SIG_IGN);

    //Listen to connection
    if (listen(socket_desc, 100) != 0) {
        //fprintf(stderr, "err#Listen to Port Failed\n: %s", strerror(errno));
        return -1;
    };
    fflush(stderr);
    while (1) {
        c = sizeof(struct sockaddr_in);

        //accept connection from an incoming client
        client_sock =
            accept(socket_desc, (struct sockaddr *)&client, (socklen_t *)&c);

        if (client_sock < 0) {
            //fprintf(stderr, "err#Accept Conn Failed: %s\n", strerror(errno));
            return -1;
        }

        char *ipAddr = inet_ntoa(((struct sockaddr_in *)&client)->sin_addr);
        fprintf(stderr, "trial#%s\n", ipAddr);

        if ((pid = fork()) < 0) {
            fprintf(stderr, "err#Fork Failed: %s\n", strerror(errno));
            return -1;
        } else if (pid == 0) {
            if (close(socket_desc) != 0) {
                //fprintf(stderr, "err#Close Listen Socket Failed: %s\n",
                //        strerror(errno));
                return -1;
            };

            if (read_client_data(client_sock, args) != 0) {
                //fprintf(stderr, "err#Read Client Data Failed: %s\n",
                //        strerror(errno));
                return -1;
            };

            if (close(client_sock) != 0) {
                //fprintf(stderr, "err#Close Client Socket Failed: %s\n",
                //        strerror(errno));
                return -1;
            };
            if (kill(getpid(), SIGKILL) != 0) {
                //fprintf(stderr, "err#Kill Child Failed: %s\n", strerror(errno));
                return -1;
            };
        }
        args->print_hint = 0;

        if (close(client_sock) != 0) {
            //fprintf(stderr, "err#Close Client Socket Failed: %s\n",
            //        strerror(errno));
            return -1;
        };
        fflush(stderr);
    }
    return 0;
}

void sendHint(const void *buffer, uintptr_t framep, struct info *args) {
    uint32_t addr = (uint32_t)buffer;

    fprintf(stderr, "ans#buffer=0x%8X|ebp=0x%8X\n", addr, framep);
    fflush(stderr);

    switch (args->level) {
        case 1:
            fprintf(stderr,
                    "hints#Buffer Address:|"
                    "0x%8X|"
                    "EBP:|"
                    "0x%8X\n",
                    addr, framep);
            break;
        case 2:
            fprintf(
                stderr,
                "hints#Buffer Address:|"
                "0x%8X|"
                "Buffer Size Range:|"
                "%u to %u\n",
                addr,
                ((BUF_SIZE - args->buf_low < 0) ? 0 : BUF_SIZE - args->buf_low),
                BUF_SIZE + args->buf_high);
            break;
        case 3:
            fprintf(
                stderr,
                "hints#Buffer Address range:|"
                "0x%8X to 0x%8X|"
                "Buffer Size Range:|"
                "%d to %d\n",
                addr & args->addr_mask, addr | ~args->addr_mask,
                ((BUF_SIZE - args->buf_low < 0) ? 0 : BUF_SIZE - args->buf_low),
                BUF_SIZE + args->buf_high);
            break;
        default: break;
    }
    fflush(stderr);
}

//function has buffer-overflow vulnerability
void bof(char *str, struct info *args) {
    char buffer[BUF_SIZE];

    uintptr_t framep;
    // Copy ebp into framep
    asm("movl %%ebp, %0" : "=r"(framep));
    if (args->print_hint) sendHint((void *)buffer, framep, args);

    strcpy(buffer, str);
}
