import { Command } from 'commander';
import inquirer from 'inquirer';
import chalk from 'chalk';
import ora from 'ora';
import { loadConfig, saveConfig } from '../config.js';
import { OpenCodeClient } from '../opencode.js';

export const setupCommand = new Command('setup')
  .description('Configurar Claudy por primera vez')
  .action(async () => {
    console.log(chalk.cyan.bold('\n🤖 Bienvenido a Claudy Setup\n'));
    console.log(chalk.gray('Configura tu asistente de IA personal en pocos pasos.\n'));

    const config = loadConfig();

    const answers = await inquirer.prompt([
      {
        type: 'list',
        name: 'authType',
        message: 'Tipo de autenticación:',
        default: config.opencode.apiKey ? 'apikey' : 'basic',
        choices: [
          { name: 'API Key (Bearer token)', value: 'apikey' },
          { name: 'Usuario + Password (Basic auth)', value: 'basic' },
          { name: 'Sin autenticación (servidor local)', value: 'none' },
        ],
      },
      {
        type: 'input',
        name: 'baseUrl',
        message: 'URL del servidor:',
        default: (a: any) =>
          a.authType === 'apikey'
            ? config.opencode.baseUrl !== 'http://127.0.0.1:4096'
              ? config.opencode.baseUrl
              : 'https://api.opencode.ai'
            : config.opencode.baseUrl || 'http://127.0.0.1:4096',
      },
      {
        type: 'password',
        name: 'apiKey',
        message: 'API Key:',
        mask: '*',
        when: (a) => a.authType === 'apikey',
        default: config.opencode.apiKey || undefined,
        validate: (input: string) =>
          input && input.length > 5 ? true : 'API key requerida',
      },
      {
        type: 'input',
        name: 'username',
        message: 'Usuario:',
        when: (a) => a.authType === 'basic',
        default: config.opencode.username || 'opencode',
      },
      {
        type: 'password',
        name: 'password',
        message: 'Password:',
        mask: '*',
        when: (a) => a.authType === 'basic',
        default: config.opencode.password || '',
      },
      {
        type: 'list',
        name: 'defaultModel',
        message: 'Modelo predeterminado (OpenCode Go):',
        default: config.opencode.defaultModel,
        choices: [
          { name: 'GLM-5', value: 'opencode-go/glm-5' },
          { name: 'GLM-5.1', value: 'opencode-go/glm-5.1' },
          { name: 'Kimi K2.5', value: 'opencode-go/kimi-k2.5' },
          { name: 'Kimi K2.6', value: 'opencode-go/kimi-k2.6' },
          { name: 'MiMo-V2-Pro', value: 'opencode-go/mimo-v2-pro' },
          { name: 'MiMo-V2-Omni', value: 'opencode-go/mimo-v2-omni' },
          { name: 'MiMo-V2.5-Pro', value: 'opencode-go/mimo-v2.5-pro' },
          { name: 'MiMo-V2.5', value: 'opencode-go/mimo-v2.5' },
          { name: 'MiniMax M2.5', value: 'opencode-go/minimax-m2.5' },
          { name: 'Qwen3.5 Plus', value: 'opencode-go/qwen3.5-plus' },
          { name: 'Qwen3.6 Plus (recomendado)', value: 'opencode-go/qwen3.6-plus' },
          { name: 'MiniMax M2.7', value: 'opencode-go/minimax-m2.7' },
          { name: 'DeepSeek V4 Pro', value: 'opencode-go/deepseek-v4-pro' },
          { name: 'DeepSeek V4 Flash', value: 'opencode-go/deepseek-v4-flash' },
          new inquirer.Separator(),
          { name: 'Otro (especificar manualmente)', value: 'custom' },
        ],
      },
      {
        type: 'input',
        name: 'customModel',
        message: 'Modelo (formato: provider/model):',
        when: (a: any) => a.defaultModel === 'custom',
        validate: (input: string) =>
          input && input.trim().length > 0 ? true : 'Modelo requerido',
      },
      {
        type: 'input',
        name: 'systemPrompt',
        message: 'System prompt (Enter para usar default):',
        default: config.agent.systemPrompt,
      },
      {
        type: 'number',
        name: 'temperature',
        message: 'Temperatura (0.0 - 1.0):',
        default: config.agent.temperature,
        validate: (input: number) => {
          if (input < 0 || input > 2) return 'Debe ser entre 0 y 2';
          return true;
        },
      },
      {
        type: 'number',
        name: 'maxTokens',
        message: 'Máximo de tokens por respuesta:',
        default: config.agent.maxTokens,
      },
    ]);

    const newConfig = {
      ...config,
      opencode: {
        baseUrl: answers.baseUrl,
        defaultModel: (answers.defaultModel === 'custom'
          ? answers.customModel
          : answers.defaultModel
        ).trim(),
        apiKey: answers.apiKey || '',
        username: answers.username || 'opencode',
        password: answers.password || '',
      },
      agent: {
        systemPrompt: answers.systemPrompt,
        temperature: answers.temperature,
        maxTokens: answers.maxTokens,
      },
    };

    const spinner = ora('Probando conexión...').start();
    const client = new OpenCodeClient(newConfig.opencode);
    const ok = await client.testConnection();

    if (!ok) {
      spinner.warn(
        chalk.yellow(
          `No se pudo conectar a ${newConfig.opencode.baseUrl}.\n` +
            '  Si usas servidor local: opencode serve --port 4096 --hostname 127.0.0.1\n' +
            '  Si usas remoto: verifica URL y API key.'
        )
      );
    } else {
      spinner.succeed(chalk.green('Conexión exitosa'));
    }

    saveConfig(newConfig);

    console.log(chalk.green.bold('\n✓ Configuración guardada\n'));
    console.log(chalk.gray('Comandos disponibles:'));
    console.log(chalk.cyan('  claudy chat       ') + chalk.gray('- Iniciar chat'));
    console.log(chalk.cyan('  claudy models     ') + chalk.gray('- Ver modelos'));
    console.log(chalk.cyan('  claudy sessions   ') + chalk.gray('- Ver sesiones'));
    console.log(chalk.cyan('  claudy config     ') + chalk.gray('- Editar config'));
    console.log('');
  });
