section .bss
    print_buf resb 32
    input_buf resb 32

section .text

global _start
global exit
global print_int
global print_string
global read_int

extern main

_start:
    call main
    mov rdi, rax
    call exit

exit:
    mov rax, 60
    syscall

; print_int(int value)
; input: rdi = integer
print_int:
    push rbp
    mov rbp, rsp
    push rbx

    mov rax, rdi
    mov rcx, print_buf + 31
    mov byte [rcx], 10
    dec rcx

    cmp rax, 0
    jne .convert

    mov byte [rcx], '0'
    jmp .print

.convert:
    mov rbx, 10

.loop:
    xor rdx, rdx
    div rbx
    add dl, '0'
    mov [rcx], dl
    dec rcx
    cmp rax, 0
    jne .loop

    inc rcx

.print:
    mov rax, 1
    mov rdi, 1
    mov rsi, rcx
    mov rdx, print_buf + 32
    sub rdx, rcx
    syscall

    pop rbx
    mov rsp, rbp
    pop rbp
    ret

; print_string(char* str)
; input: rdi = address of null-terminated string
print_string:
    push rbp
    mov rbp, rsp

    mov rsi, rdi
    xor rdx, rdx

.count_loop:
    cmp byte [rsi + rdx], 0
    je .write
    inc rdx
    jmp .count_loop

.write:
    mov rax, 1
    mov rdi, 1
    syscall

    mov rsp, rbp
    pop rbp
    ret

; read_int()
; output: rax = parsed integer
read_int:
    push rbp
    mov rbp, rsp

    mov rax, 0
    mov rdi, 0
    mov rsi, input_buf
    mov rdx, 32
    syscall

    mov rsi, input_buf
    xor rax, rax
    xor r8, r8

    cmp byte [rsi], '-'
    jne .parse_loop
    mov r8, 1
    inc rsi

.parse_loop:
    movzx rdx, byte [rsi]

    cmp rdx, 10
    je .done
    cmp rdx, 0
    je .done

    cmp rdx, '0'
    jl .done
    cmp rdx, '9'
    jg .done

    sub rdx, '0'
    imul rax, rax, 10
    add rax, rdx

    inc rsi
    jmp .parse_loop

.done:
    cmp r8, 0
    je .return
    neg rax

.return:
    mov rsp, rbp
    pop rbp
    ret