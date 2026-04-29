section .text

global _start
global exit

extern main

_start:
    call main
    mov rdi, rax
    call exit

exit:
    mov rax, 60
    syscall