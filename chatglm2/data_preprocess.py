from datasets import load_dataset

def print_dataset_example(example,tokenizer):
    print("input_ids",example["input_ids"])
    print("inputs", tokenizer.decode(example["input_ids"]))
    print("label_ids", example["labels"])
    print("labels", tokenizer.decode(example["labels"]))

def load_raw_datasets(data_args,cache_dir):
    data_files = {}
    if data_args.train_file is not None:
        data_files["train"] = data_args.train_file
    if data_args.validation_file is not None:
        data_files["validation"] = data_args.validation_file
    if data_args.test_file is not None:
        data_files["test"] = data_args.test_file

    # 加载数据集
    raw_datasets = load_dataset(
        "json",
        data_files=data_files,
        cache_dir=cache_dir
    )

    return raw_datasets

class Preprocessor:
    
    def __init__(self,data_args,tokenizer):
        self.prompt_column = data_args.prompt_column
        self.response_column = data_args.response_column
        self.max_source_length = data_args.max_source_length
        self.max_target_length = data_args.max_target_length
        self.tokenizer = tokenizer
        self.ignore_pad_token_for_loss = data_args.ignore_pad_token_for_loss
    
    # 处理测试(dev/test)数据
    '''
        测试数据的拼接方式：[pad][pad]...[gmask_token][sop_token]输入文本[pad][pad]....输出文本
    '''
    def preprocess_function_eval(self,examples):  
        inputs, targets = [], []

        # 读取input/output即prompt/response字段的文本
        inputs, targets = [], []
        for i in range(len(examples[self.prompt_column])):
            if examples[self.prompt_column][i] and examples[self.response_column][i]:
                query = examples[self.prompt_column][i]
                prompt = self.tokenizer.build_prompt(query)
                inputs.append(prompt)
                targets.append(examples[self.response_column][i])

        self.tokenizer.truncation_side = 'left'

        # 对输入文本（prompt）做tokenize
        model_inputs = self.tokenizer(
            inputs, 
            max_length=self.max_source_length, 
            truncation=True, 
            padding=True
        )

        # 对输出文本（response）做tokenize
        labels = self.tokenizer(
            text_target=targets, 
            max_length=self.max_target_length, 
            truncation=True, 
            padding=True
        )

        # 如果对pad token不进行loss计算，则将pad token标识为-100（模型约定的值）
        if self.ignore_pad_token_for_loss:
            labels["input_ids"] = [
                [(l if l != self.tokenizer.pad_token_id else -100) for l in label] for label in labels["input_ids"]
            ]
        model_inputs["labels"] = labels["input_ids"]

        return model_inputs


    # 处理训练(train)数据
    '''
        训练数据的拼接方式：[gmask_token][sop_token]输入文本输出文本[eos_token][pad][pad]....
    '''
    def preprocess_function_train(self,examples):
        max_seq_length = self.max_source_length + self.max_target_length

        model_inputs = {
            "input_ids": [],
            "labels": [],
        }
        for i in range(len(examples[self.prompt_column])):
            if examples[self.prompt_column][i] and examples[self.response_column][i]:
                query, answer = examples[self.prompt_column][i], examples[self.response_column][i]
                prompt = self.tokenizer.build_prompt(query)
                a_ids = self.tokenizer.encode(
                    text=prompt, 
                    add_special_tokens=True, 
                    truncation=True,
                    max_length=self.max_source_length
                )
                b_ids = self.tokenizer.encode(
                    text=answer, 
                    add_special_tokens=False, 
                    truncation=True,
                    max_length=self.max_target_length
                )

			
                context_length = len(a_ids)

                # 手工拼接
                input_ids = a_ids + b_ids + [self.tokenizer.eos_token_id]
                
                # 手工pad
                labels = [self.tokenizer.pad_token_id] * context_length + b_ids + [self.tokenizer.eos_token_id]
                
                pad_len = max_seq_length - len(input_ids)
                input_ids = input_ids + [self.tokenizer.pad_token_id] * pad_len
                labels = labels + [self.tokenizer.pad_token_id] * pad_len

                # 如果对pad token不进行loss计算，则将pad token标识为-100（模型约定的值）
                if self.ignore_pad_token_for_loss:
                    labels = [(l if l != self.tokenizer.pad_token_id else -100) for l in labels]	

                model_inputs["input_ids"].append(input_ids)
                model_inputs["labels"].append(labels)


        return model_inputs